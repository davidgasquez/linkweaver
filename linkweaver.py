import argparse
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib import request
from urllib.parse import urlparse

from markitdown import MarkItDown  # type: ignore[unresolved-import]

PLAINTEXT_EXTENSIONS = {
    ".adoc",
    ".asc",
    ".csv",
    ".ini",
    ".json",
    ".jsonl",
    ".log",
    ".markdown",
    ".md",
    ".mdown",
    ".rst",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

PLAINTEXT_CONTENT_TYPES = {
    "application/json",
    "application/toml",
    "application/x-yaml",
    "application/xml",
    "application/yaml",
    "text/xml",
}


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        for attr in dir(cls):
            if attr.isupper():
                setattr(cls, attr, "")


if not sys.stdout.isatty():
    Colors.disable()


def warn(message: str) -> None:
    print(f"{Colors.YELLOW}{message}{Colors.RESET}", file=sys.stderr)


def die(message: str) -> None:
    print(f"{Colors.RED}Error: {message}{Colors.RESET}", file=sys.stderr)
    raise SystemExit(1)


def is_valid_url(url: str) -> tuple[bool, str | None]:
    url = url.strip()
    if not url:
        return False, "Empty URL"
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    parsed = urlparse(url)
    if not parsed.netloc:
        return False, "URL missing domain name"
    if (
        ".." in parsed.netloc
        or parsed.netloc.startswith(".")
        or parsed.netloc.endswith(".")
    ):
        return False, "Malformed domain name"
    if any(char in parsed.netloc for char in ["<", ">", '"', "'", "`"]):
        return False, "Invalid characters in domain name"

    return True, None


def read_file(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_path.is_dir():
        raise IsADirectoryError(f"Expected file but found directory: {file_path}")
    return file_path.read_text(encoding="utf-8")


def _trim_bare_url(url: str) -> str:
    url = url.rstrip(".,;:!?")
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    while url.endswith("]") and url.count("]") > url.count("["):
        url = url[:-1]
    while url.endswith("}") and url.count("}") > url.count("{"):
        url = url[:-1]
    return url


def _markdown_destinations(content: str) -> list[str]:
    urls = []
    index = 0

    while True:
        start = content.find("](", index)
        if start == -1:
            return urls

        pos = start + 2
        depth = 0
        escaped = False
        while pos < len(content):
            char = content[pos]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    destination = content[start + 2 : pos].strip()
                    urls.append(_normalize_markdown_destination(destination))
                    break
                depth -= 1
            pos += 1

        index = pos + 1


def _normalize_markdown_destination(destination: str) -> str:
    if destination.startswith("<"):
        end = destination.find(">")
        if end != -1:
            return destination[1:end].strip()
    return destination.split(maxsplit=1)[0] if destination else destination


def extract_urls(content: str) -> set[str]:
    urls: set[str] = set()
    invalid_urls: list[tuple[str, str]] = []

    candidates = _markdown_destinations(content)
    candidates.extend(
        _trim_bare_url(match.group(0))
        for match in re.finditer(r"https?://[^\s<>'\"]+", content)
    )

    for url in candidates:
        is_valid, error = is_valid_url(url)
        if is_valid:
            urls.add(url.strip())
        elif error is not None:
            invalid_urls.append((url, error))

    if invalid_urls:
        warn(f"Warning: Found {len(invalid_urls)} invalid URLs:")
        for url, error in invalid_urls:
            print(f"  {Colors.RED}x{Colors.RESET} {url}: {error}", file=sys.stderr)
        warn("Suggestion: Check URL formatting and fix malformed links")

    return urls


def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    filename = (parsed.netloc or "unknown-domain").replace(".", "-")

    if parsed.path and parsed.path != "/":
        path = re.sub(r'[/\\?%*:|"<>\s]+', "-", parsed.path.strip("/"))
        filename += f"-{path}"

    if parsed.query:
        query = re.sub(r'[=&?%*:|"<>\s]+', "-", parsed.query)
        filename += f"-{query[:50]}"

    filename = re.sub(r"-+", "-", filename).strip("-")
    return filename if filename.endswith(".md") else f"{filename}.md"


def _resource_dir(file_path: Path, output_dir: Path | None = None) -> Path:
    if output_dir is not None:
        return output_dir
    return file_path.parent / f"{file_path.stem}-resources"


def _ensure_output_dir(directory: Path) -> None:
    if directory.exists() and not directory.is_dir():
        die(f"{directory} exists and is not a directory")

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        die(f"Cannot create directory {directory}: {error}")


def _print_read_error(file_path: Path, error: Exception) -> None:
    if isinstance(error, FileNotFoundError):
        die(f"{file_path}\nSuggestion: Check the file path and ensure it exists")
    if isinstance(error, IsADirectoryError):
        die(f"{file_path} is a directory\nSuggestion: Provide a file path")
    if isinstance(error, PermissionError):
        die(
            f"Permission denied reading {file_path}\nSuggestion: Check file permissions"
        )
    if isinstance(error, UnicodeDecodeError):
        die(
            f"Unable to decode {file_path} as UTF-8\n"
            "Suggestion: Convert the file to UTF-8"
        )
    die(f"Could not read {file_path}: {error}")


def collect_urls(
    input_files: list[Path], verbose: bool = False, quiet: bool = False
) -> dict[Path, set[str]]:
    urls_by_file: dict[Path, set[str]] = {}

    for file_path in input_files:
        if not quiet:
            print(
                f"{Colors.CYAN}Extracting URLs from {file_path.name}...{Colors.RESET}"
            )
        try:
            content = read_file(file_path)
        except Exception as error:
            _print_read_error(file_path, error)

        urls = extract_urls(content)
        urls_by_file[file_path] = urls

        if urls and not quiet:
            print(
                f"{Colors.GREEN}Found {len(urls)} URLs in {file_path.name}{Colors.RESET}"
            )
        elif verbose and not quiet:
            print(f"{Colors.YELLOW}No URLs found in {file_path.name}{Colors.RESET}")

    return urls_by_file


def _write_error_file(
    output_path: Path, url: str, error: Exception, retries: int
) -> None:
    content = (
        "# Failed to fetch content\n\n"
        f"**Source:** {url}\n\n"
        f"**Error:** {type(error).__name__}: {error}\n\n"
        f"**Retries attempted:** {retries}\n\n"
        f"This URL could not be processed after {retries} retry attempts."
    )
    output_path.write_text(content, encoding="utf-8")
    print(f"  {Colors.YELLOW}Error logged: {output_path.name}{Colors.RESET}")


class NonPlaintextResponseError(Exception):
    pass


def _is_plaintext_url(url: str) -> bool:
    return Path(urlparse(url).path.lower()).suffix in PLAINTEXT_EXTENSIONS


def _is_plaintext_content_type(content_type: str) -> bool:
    if content_type == "text/html":
        return False
    return content_type.startswith("text/") or content_type in PLAINTEXT_CONTENT_TYPES


def _fetch_plaintext(url: str) -> str:
    url_request = request.Request(url, headers={"User-Agent": "linkweaver"})
    with request.urlopen(url_request, timeout=30) as response:
        content_type = response.headers.get_content_type()
        if not _is_plaintext_content_type(content_type):
            raise NonPlaintextResponseError(
                f"{url} returned {content_type}, not plaintext"
            )
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _convert_url(md: MarkItDown | None, url: str) -> str:
    if _is_plaintext_url(url):
        try:
            content = _fetch_plaintext(url)
            if not content.strip():
                raise RuntimeError("plaintext content is empty")
            return content
        except NonPlaintextResponseError:
            pass

    if md is None:
        md = MarkItDown(enable_builtins=True)

    result = md.convert(url)
    title = result.title or "Untitled"
    content = result.markdown or ""
    if not content.strip():
        raise RuntimeError("converted markdown content is empty")
    return f"# {title}\n\n**Source:** {url}\n\n{content}"


def _fetch_with_retries(
    md: MarkItDown | None,
    url: str,
    max_retries: int,
    verbose: bool,
) -> str:
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = (2 ** (attempt - 1)) + random.uniform(0, 1)
            if verbose:
                print(
                    f"  {Colors.YELLOW}Retry {attempt}/{max_retries} "
                    f"after {delay:.1f}s delay{Colors.RESET}"
                )
            time.sleep(delay)

        try:
            return _convert_url(md, url)
        except Exception as error:
            last_error = error
            if attempt < max_retries:
                print(
                    f"  {Colors.YELLOW}{type(error).__name__}: {error}"
                    f" (attempt {attempt + 1}/{max_retries + 1}){Colors.RESET}"
                )

    if last_error is None:
        raise RuntimeError("conversion failed without an error")
    raise last_error


def fetch_and_save_urls(
    urls: set[str],
    output_dir: Path,
    verbose: bool = False,
    max_retries: int = 3,
    quiet: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    if not urls:
        if not quiet:
            print(f"{Colors.YELLOW}No URLs found to process.{Colors.RESET}")
        return

    sorted_urls = sorted(urls)
    if not quiet:
        print(
            f"{Colors.CYAN}Processing {len(sorted_urls)} unique URLs...{Colors.RESET}"
        )

    md: MarkItDown | None = None

    for index, url in enumerate(sorted_urls, 1):
        filename = url_to_filename(url)
        output_path = output_dir / filename

        if not quiet:
            print(
                f"{Colors.BLUE}[{index}/{len(sorted_urls)}]{Colors.RESET} Fetching: {url}"
            )

        if output_path.exists() and not force:
            if not quiet:
                action = "Would skip" if dry_run else "Skipping"
                print(f"  {Colors.BLUE}{action} (exists): {filename}{Colors.RESET}")
            continue

        if dry_run:
            if not quiet:
                print(
                    f"  {Colors.CYAN}Would fetch and save to: {filename}{Colors.RESET}"
                )
            continue

        if not _is_plaintext_url(url) and md is None:
            md = MarkItDown(enable_builtins=True)

        try:
            output = _fetch_with_retries(md, url, max_retries, verbose and not quiet)
            output_path.write_text(output, encoding="utf-8")
            if not quiet:
                print(f"  {Colors.GREEN}Saved: {filename}{Colors.RESET}")
        except Exception as error:
            print(
                f"  {Colors.RED}Failed after {max_retries} retries: "
                f"{type(error).__name__}: {error}{Colors.RESET}"
            )
            _write_error_file(output_path, url, error, max_retries)


def list_links(
    input_files: list[Path],
    verbose: bool = False,
    quiet: bool = False,
    dry_run: bool = False,
) -> None:
    urls_by_file = collect_urls(input_files, verbose, quiet=True)
    all_urls = set().union(*urls_by_file.values()) if urls_by_file else set()

    if not all_urls:
        warn("No URLs found in any files.")
        return

    if verbose and not quiet:
        print(
            f"{Colors.CYAN}Found {len(all_urls)} unique URLs total{Colors.RESET}",
            file=sys.stderr,
        )

    if dry_run:
        if not quiet:
            print(
                f"{Colors.CYAN}Would list {len(all_urls)} unique URLs{Colors.RESET}",
                file=sys.stderr,
            )
        return

    for url in sorted(all_urls):
        print(url)


def process_files(
    input_files: list[Path],
    verbose: bool = False,
    max_retries: int = 3,
    quiet: bool = False,
    dry_run: bool = False,
    force: bool = False,
    output_dir: Path | None = None,
) -> None:
    urls_by_file = collect_urls(input_files, verbose, quiet)
    all_urls = set().union(*urls_by_file.values()) if urls_by_file else set()

    if not all_urls:
        if not quiet:
            print(f"{Colors.YELLOW}No URLs found in any files.{Colors.RESET}")
        return

    if not quiet:
        print(f"\n{Colors.BOLD}Total unique URLs found: {len(all_urls)}{Colors.RESET}")

    for file_path, urls in urls_by_file.items():
        if not urls:
            continue

        resource_dir = _resource_dir(file_path, output_dir)
        if not dry_run:
            _ensure_output_dir(resource_dir)

        if not quiet:
            action = "Would create and process" if dry_run else "Processing"
            print(
                f"\n{Colors.MAGENTA}{action} {file_path.name} -> "
                f"{resource_dir}/{Colors.RESET}"
            )

        fetch_and_save_urls(
            urls,
            resource_dir,
            verbose=verbose,
            max_retries=max_retries,
            quiet=quiet,
            dry_run=dry_run,
            force=force,
        )


def cli() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract URLs from markdown files and save each link as individual "
            "markdown files in resource folders.\n"
            "By default, existing files are skipped to save time and bandwidth."
        ),
        epilog=(
            "Examples:\n"
            "  linkweaver notes.md                      # Process file, skip existing resources\n"
            "  linkweaver --force notes.md              # Force redownload all resources\n"
            "  linkweaver --list-links notes.md         # List all URLs found\n"
            "  linkweaver -o resources notes.md         # Save resources to a specific folder\n"
            "  linkweaver --retries 5 notes.md          # Use 5 retry attempts for failed URLs\n"
            "  linkweaver --quiet --dry-run notes.md    # Preview actions quietly\n"
            "  linkweaver -q -v notes.md                # Quiet mode overrides verbose\n"
            "  linkweaver --no-color notes.md           # Disable colored output\n"
            "\n"
            "Common workflows:\n"
            "  linkweaver --list-links *.md | head -10  # Preview first 10 URLs\n"
            "  linkweaver --dry-run notes.md            # See what would be fetched/skipped\n"
            "  linkweaver --force --dry-run notes.md    # Preview forced redownload\n"
            "  linkweaver --retries 0 notes.md          # Disable retries for speed"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input_files",
        nargs="*",
        type=Path,
        help="One or more markdown files to process",
    )
    parser.add_argument(
        "--list-links",
        "-l",
        action="store_true",
        help="List all unique URLs found in the files without downloading",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        metavar="DIR",
        help="Save resource files to this folder",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed progress output",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Number of retry attempts for failed URL fetches",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimize output while still showing warnings and errors",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files or fetching URLs",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Redownload files even if resource files already exist",
    )

    args = parser.parse_args()

    if args.retries < 0:
        die("--retries must be a non-negative integer")

    if args.no_color or os.environ.get("NO_COLOR"):
        Colors.disable()

    if not args.input_files:
        parser.print_help()
        raise SystemExit(0)

    try:
        if args.list_links:
            list_links(args.input_files, args.verbose, args.quiet, args.dry_run)
        else:
            process_files(
                args.input_files,
                args.verbose,
                args.retries,
                args.quiet,
                args.dry_run,
                args.force,
                args.output_dir,
            )
    except KeyboardInterrupt:
        warn("Operation cancelled by user")
        raise SystemExit(130) from None


if __name__ == "__main__":
    cli()
