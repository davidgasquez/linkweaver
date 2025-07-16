import argparse
import os
import random
import re
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from markitdown import MarkItDown


# Color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        """Disable colors for non-terminal output."""
        for attr in dir(cls):
            if not attr.startswith("_") and attr != "disable":
                setattr(cls, attr, "")


# Disable colors if not in a terminal
if not sys.stdout.isatty():
    Colors.disable()


def is_valid_url(url: str) -> tuple[bool, Optional[str]]:
    """Validate URL format and return (is_valid, error_message)."""
    if not url or not url.strip():
        return False, "Empty URL"

    url = url.strip()

    # Check for basic URL format
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "URL must start with http:// or https://"

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, "URL missing domain name"

        # Check for obvious malformed URLs
        if (
            ".." in parsed.netloc
            or parsed.netloc.startswith(".")
            or parsed.netloc.endswith(".")
        ):
            return False, "Malformed domain name"

        # Check for suspicious characters in domain
        if any(char in parsed.netloc for char in ["<", ">", '"', "'", "`"]):
            return False, "Invalid characters in domain name"

        return True, None
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


def read_file(file_path: Path) -> str:
    """Read content from a file with better error handling."""
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"File not found: {file_path}\nSuggestion: Check the file path and ensure the file exists"
        )
    except PermissionError:
        raise PermissionError(
            f"Permission denied reading file: {file_path}\nSuggestion: Check file permissions or run with appropriate privileges"
        )
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            e.encoding,
            e.object,
            e.start,
            e.end,
            f"Unable to decode file {file_path} as UTF-8\nSuggestion: Try converting the file to UTF-8 encoding or specify a different encoding",
        )
    except IsADirectoryError:
        raise IsADirectoryError(
            f"Expected file but found directory: {file_path}\nSuggestion: Provide a file path, not a directory"
        )
    except OSError as e:
        raise OSError(
            f"Error reading file {file_path}: {e}\nSuggestion: Check if the file is corrupted or on a mounted filesystem"
        )


def extract_urls(content: str) -> set[str]:
    """Extract all URLs from markdown content with validation."""
    urls = set()
    invalid_urls = []

    # Pattern for markdown links: [text](url)
    markdown_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
    for _, url in markdown_links:
        url = url.strip()
        is_valid, error = is_valid_url(url)
        if is_valid:
            urls.add(url)
        else:
            invalid_urls.append((url, error))

    # Pattern for bare URLs (http/https)
    bare_urls = re.findall(r"https?://[^\s\)]+", content)
    for url in bare_urls:
        # Clean up any trailing punctuation
        url = url.rstrip(".,;:!?)")
        is_valid, error = is_valid_url(url)
        if is_valid:
            urls.add(url)
        else:
            invalid_urls.append((url, error))

    # Report invalid URLs
    if invalid_urls:
        print(
            f"{Colors.YELLOW}Warning: Found {len(invalid_urls)} invalid URLs:{Colors.RESET}",
            file=sys.stderr,
        )
        for url, error in invalid_urls:
            print(f"  {Colors.RED}✗{Colors.RESET} {url}: {error}", file=sys.stderr)
        print(
            f"{Colors.YELLOW}Suggestion: Check URL formatting and fix malformed links{Colors.RESET}",
            file=sys.stderr,
        )

    return urls


def url_to_filename(url: str) -> str:
    """Convert URL to a clean filename."""
    parsed = urlparse(url)

    # Start with domain, replacing dots with hyphens
    filename = parsed.netloc or "unknown-domain"
    filename = filename.replace(".", "-")

    # Add path, replacing slashes and special chars with hyphens
    if parsed.path and parsed.path != "/":
        path = parsed.path.strip("/")
        # Replace problematic characters with hyphens
        path = re.sub(r'[/\\?%*:|"<>\s]+', "-", path)
        filename += f"-{path}"

    # Add query params if present (simplified)
    if parsed.query:
        query = re.sub(r'[=&?%*:|"<>\s]+', "-", parsed.query)
        filename += f"-{query[:50]}"  # Limit length

    # Clean up multiple hyphens and ensure it ends with .md
    filename = re.sub(r"-+", "-", filename).strip("-")
    return f"{filename}.md"


def _format_url_error(e: URLError, url: str) -> str:
    """Format URL error with actionable suggestions."""
    if isinstance(e, HTTPError):
        if e.code == 404:
            return f"Page not found (404) for {url}\nSuggestion: Check if the URL is correct and the page exists"
        elif e.code == 403:
            return f"Access forbidden (403) for {url}\nSuggestion: The site may block automated requests or require authentication"
        elif e.code == 500:
            return f"Server error (500) for {url}\nSuggestion: The website is experiencing issues, try again later"
        elif e.code == 503:
            return f"Service unavailable (503) for {url}\nSuggestion: The website is temporarily down, try again later"
        else:
            return f"HTTP error {e.code} for {url}\nSuggestion: Check if the URL is correct and accessible"
    else:
        return f"Network error for {url}: {str(e)}\nSuggestion: Check internet connection and URL accessibility"


def _create_error_file(output_path: Path, url: str, error_msg: str) -> None:
    """Create error file with failure details."""
    try:
        error_content = (
            f"# Failed to fetch content\n\n**Source:** {url}\n\n**Error:** {error_msg}"
        )
        output_path.write_text(error_content, encoding="utf-8")
        print(f"  {Colors.YELLOW}✓ Error logged: {output_path.name}{Colors.RESET}")
    except Exception as write_error:
        print(
            f"  {Colors.RED}✗ Could not write error file: {write_error}{Colors.RESET}"
        )


def fetch_and_save_urls(
    urls: set[str],
    output_dir: Path,
    exec_cmd: str | None = None,
    verbose: bool = False,
    max_retries: int = 3,
    quiet: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Fetch content from URLs and save each as individual markdown files.

    Args:
        urls: Set of URLs to fetch
        output_dir: Directory to save fetched content
        exec_cmd: Optional command to process content before saving
        verbose: Enable verbose output
        max_retries: Maximum number of retry attempts for failed fetches (default: 3)
        quiet: Minimize output (opposite of verbose, but still show errors/warnings)
        dry_run: Show what would be done without actually doing it
        force: Force redownload even if file already exists
    """
    if not urls:
        print(f"{Colors.YELLOW}No URLs found to process.{Colors.RESET}")
        return

    sorted_urls = sorted(urls)
    total = len(sorted_urls)

    if not quiet:
        print(
            f"{Colors.CYAN}Processing {total} unique URLs using markitdown...{Colors.RESET}"
        )

    md = MarkItDown(enable_builtins=True) if not dry_run else None

    for i, url in enumerate(sorted_urls, 1):
        filename = url_to_filename(url)
        output_path = output_dir / filename

        # Simple progress indicator
        progress_num = f"[{i}/{total}]"

        if not quiet:
            print(f"{Colors.BLUE}{progress_num}{Colors.RESET} Fetching: {url}")

        # Handle dry-run mode
        if dry_run:
            if not quiet:
                if output_path.exists() and not force:
                    print(
                        f"  {Colors.CYAN}Would skip (file exists): {filename}{Colors.RESET}"
                    )
                else:
                    print(
                        f"  {Colors.CYAN}Would fetch and save to: {filename}{Colors.RESET}"
                    )
            continue

        # Check if file exists and skip if not forcing redownload
        if output_path.exists() and not force:
            if not quiet:
                print(f"  {Colors.BLUE}→ Skipping (exists): {filename}{Colors.RESET}")
            continue

        # Ensure md is available for non-dry-run mode
        if md is None:
            continue  # This should not happen, but guard against it

        # Retry logic with exponential backoff
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff: base delay of 1s, doubled each retry with jitter
                    delay = (2 ** (attempt - 1)) + random.uniform(0, 1)
                    if verbose and not quiet:
                        print(
                            f"  {Colors.YELLOW}Retry {attempt}/{max_retries} after {delay:.1f}s delay{Colors.RESET}"
                        )
                    time.sleep(delay)

                result = md.convert(url)
                title = result.title or "Untitled"
                content = result.markdown or ""

                # Add metadata header to the markdown file
                full_content = f"# {title}\n\n**Source:** {url}\n\n{content}"

                # Process content through exec command if provided
                if exec_cmd:
                    try:
                        result = subprocess.run(
                            exec_cmd,
                            shell=True,
                            input=full_content,
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=60,
                        )
                        full_content = result.stdout
                        if verbose and not quiet:
                            print(
                                f"  {Colors.CYAN}Processed with exec command{Colors.RESET}"
                            )
                    except subprocess.CalledProcessError as e:
                        stderr_output = (
                            e.stderr.strip() if e.stderr else "No error details"
                        )
                        print(
                            f"  {Colors.YELLOW}Warning: exec command failed (exit code {e.returncode}): {stderr_output}{Colors.RESET}"
                        )
                        print(f"  {Colors.YELLOW}Command: {exec_cmd}{Colors.RESET}")
                        print(
                            f"  {Colors.YELLOW}Suggestion: Check command syntax and ensure required tools are installed{Colors.RESET}"
                        )
                        print(f"  {Colors.YELLOW}Using original content{Colors.RESET}")
                    except subprocess.TimeoutExpired:
                        print(
                            f"  {Colors.YELLOW}Warning: exec command timed out after 60s{Colors.RESET}"
                        )
                        print(f"  {Colors.YELLOW}Command: {exec_cmd}{Colors.RESET}")
                        print(
                            f"  {Colors.YELLOW}Suggestion: Simplify command or increase timeout if needed{Colors.RESET}"
                        )
                        print(f"  {Colors.YELLOW}Using original content{Colors.RESET}")
                    except FileNotFoundError:
                        print(
                            f"  {Colors.YELLOW}Warning: exec command not found: {exec_cmd}{Colors.RESET}"
                        )
                        print(
                            f"  {Colors.YELLOW}Suggestion: Check if the command is installed and in PATH{Colors.RESET}"
                        )
                        print(f"  {Colors.YELLOW}Using original content{Colors.RESET}")

                output_path.write_text(full_content, encoding="utf-8")
                if not quiet:
                    print(f"  {Colors.GREEN}✓ Saved: {filename}{Colors.RESET}")
                break  # Success, exit retry loop

            except URLError as e:
                error_msg = _format_url_error(e, url)
                if attempt == 0:
                    print(
                        f"  {Colors.YELLOW}⚠ Network error: {error_msg.split('Suggestion:')[0].strip()}{Colors.RESET}"
                    )
                elif attempt < max_retries:
                    print(
                        f"  {Colors.YELLOW}⚠ Network error (attempt {attempt + 1}){Colors.RESET}"
                    )
                else:
                    print(
                        f"  {Colors.RED}✗ Network error after {max_retries} retries: {error_msg.split('Suggestion:')[0].strip()}{Colors.RESET}"
                    )
                    print(
                        f"  {Colors.YELLOW}{error_msg.split('Suggestion:')[1].strip() if 'Suggestion:' in error_msg else 'Try again later'}{Colors.RESET}"
                    )
                    _create_error_file(output_path, url, error_msg)
                    break

                if attempt < max_retries:
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)

            except socket.timeout:
                error_msg = f"Connection timed out for {url}"
                if attempt == 0:
                    print(f"  {Colors.YELLOW}⚠ {error_msg}{Colors.RESET}")
                elif attempt < max_retries:
                    print(
                        f"  {Colors.YELLOW}⚠ Timeout (attempt {attempt + 1}){Colors.RESET}"
                    )
                else:
                    print(
                        f"  {Colors.RED}✗ {error_msg} after {max_retries} retries{Colors.RESET}"
                    )
                    print(
                        f"  {Colors.YELLOW}Suggestion: Check internet connection or try again later{Colors.RESET}"
                    )
                    _create_error_file(output_path, url, error_msg)
                    break

                if attempt < max_retries:
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)

            except socket.gaierror as e:
                error_msg = f"DNS resolution failed for {url}: {e}"
                if attempt == 0:
                    print(f"  {Colors.YELLOW}⚠ DNS error: {e}{Colors.RESET}")
                elif attempt < max_retries:
                    print(
                        f"  {Colors.YELLOW}⚠ DNS error (attempt {attempt + 1}){Colors.RESET}"
                    )
                else:
                    print(
                        f"  {Colors.RED}✗ {error_msg} after {max_retries} retries{Colors.RESET}"
                    )
                    print(
                        f"  {Colors.YELLOW}Suggestion: Check the domain name and your DNS settings{Colors.RESET}"
                    )
                    _create_error_file(output_path, url, error_msg)
                    break

                if attempt < max_retries:
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)

            except ssl.SSLError as e:
                error_msg = f"SSL/TLS error for {url}: {e}"
                if attempt == 0:
                    print(f"  {Colors.YELLOW}⚠ SSL error: {e}{Colors.RESET}")
                elif attempt < max_retries:
                    print(
                        f"  {Colors.YELLOW}⚠ SSL error (attempt {attempt + 1}){Colors.RESET}"
                    )
                else:
                    print(
                        f"  {Colors.RED}✗ {error_msg} after {max_retries} retries{Colors.RESET}"
                    )
                    print(
                        f"  {Colors.YELLOW}Suggestion: Check if the site has valid SSL certificate or try HTTP instead{Colors.RESET}"
                    )
                    _create_error_file(output_path, url, error_msg)
                    break

                if attempt < max_retries:
                    delay = (2**attempt) + random.uniform(0, 1)
                    time.sleep(delay)

            except Exception as e:
                error_type = type(e).__name__

                if attempt == 0:
                    print(f"  {Colors.YELLOW}⚠ {error_type}: {e}{Colors.RESET}")
                elif attempt < max_retries:
                    print(
                        f"  {Colors.YELLOW}⚠ {error_type} (attempt {attempt + 1}){Colors.RESET}"
                    )
                else:
                    print(
                        f"  {Colors.RED}✗ Failed after {max_retries} retries: {url} - {error_type}: {e}{Colors.RESET}"
                    )
                    print(
                        f"  {Colors.YELLOW}Suggestion: Check if the URL is accessible and try again{Colors.RESET}"
                    )

                    error_content = (
                        f"# Failed to fetch content\n\n**Source:** {url}\n\n"
                        f"**Error:** {error_type}: {str(e)}\n\n"
                        f"**Retries attempted:** {max_retries}\n\n"
                        f"This URL could not be fetched after {max_retries} retry attempts."
                    )
                    output_path.write_text(error_content, encoding="utf-8")
                    if not quiet:
                        print(
                            f"  {Colors.YELLOW}✓ Error logged: {filename}{Colors.RESET}"
                        )
                    break


def xml_cat_files(
    input_files: list[Path],
    verbose: bool = False,
    quiet: bool = False,
    dry_run: bool = False,
) -> None:
    """Concatenate input files and their resource folders in XML structure."""
    missing_files = []

    for file_path in input_files:
        if not file_path.exists():
            missing_files.append(file_path)
            continue

        # Get the corresponding resource folder
        resource_dir = file_path.parent / f"{file_path.stem}-resources"

        if verbose and not quiet:
            print(
                f"{Colors.CYAN}Processing {file_path.name}...{Colors.RESET}",
                file=sys.stderr,
            )

        # Start with the original file
        if dry_run:
            if not quiet:
                print(
                    f"  {Colors.CYAN}Would output document: {file_path.name}{Colors.RESET}",
                    file=sys.stderr,
                )
                if resource_dir.exists():
                    md_files = list(resource_dir.glob("*.md"))
                    if md_files:
                        print(
                            f"  {Colors.CYAN}Would include {len(md_files)} resource files{Colors.RESET}",
                            file=sys.stderr,
                        )
        else:
            print(f"<document source='{file_path.name}'>")
            try:
                original_content = read_file(file_path)
                print(original_content)
            except FileNotFoundError:
                print(
                    f"{Colors.RED}Error: File not found: {file_path.name}{Colors.RESET}",
                    file=sys.stderr,
                )
                print(
                    f"{Colors.YELLOW}Suggestion: Check the file path and ensure the file exists{Colors.RESET}",
                    file=sys.stderr,
                )
                continue
            except PermissionError:
                print(
                    f"{Colors.RED}Error: Permission denied reading {file_path.name}{Colors.RESET}",
                    file=sys.stderr,
                )
                print(
                    f"{Colors.YELLOW}Suggestion: Check file permissions or run with appropriate privileges{Colors.RESET}",
                    file=sys.stderr,
                )
                continue
            except UnicodeDecodeError:
                print(
                    f"{Colors.RED}Error: Unable to decode {file_path.name} as UTF-8{Colors.RESET}",
                    file=sys.stderr,
                )
                print(
                    f"{Colors.YELLOW}Suggestion: Convert the file to UTF-8 encoding{Colors.RESET}",
                    file=sys.stderr,
                )
                continue
            except Exception as e:
                print(
                    f"{Colors.RED}Error reading {file_path.name}: {e}{Colors.RESET}",
                    file=sys.stderr,
                )
                print(
                    f"{Colors.YELLOW}Suggestion: Check if the file is corrupted or try again{Colors.RESET}",
                    file=sys.stderr,
                )
                continue

        # Add resource files if they exist
        if not dry_run:
            if resource_dir.exists() and resource_dir.is_dir():
                md_files = list(resource_dir.glob("*.md"))
                if md_files:
                    print("\n<resources>")
                    # Sort files for consistent output
                    md_files.sort(key=lambda x: x.name)

                    for md_file in md_files:
                        print(f"\n<resource file='{md_file.name}'>")
                        try:
                            content = read_file(md_file)
                            print(content)
                        except FileNotFoundError:
                            print(
                                f"{Colors.RED}Error: Resource file not found: {md_file.name}{Colors.RESET}",
                                file=sys.stderr,
                            )
                        except PermissionError:
                            print(
                                f"{Colors.RED}Error: Permission denied reading resource file: {md_file.name}{Colors.RESET}",
                                file=sys.stderr,
                            )
                        except UnicodeDecodeError:
                            print(
                                f"{Colors.RED}Error: Unable to decode resource file {md_file.name} as UTF-8{Colors.RESET}",
                                file=sys.stderr,
                            )
                        except Exception as e:
                            print(
                                f"{Colors.RED}Error reading {md_file.name}: {e}{Colors.RESET}",
                                file=sys.stderr,
                            )
                        print("</resource>")
                    print("\n</resources>")
                elif verbose and not quiet:
                    print(
                        f"{Colors.YELLOW}No resource files found in {resource_dir.name}{Colors.RESET}",
                        file=sys.stderr,
                    )
            elif verbose and not quiet:
                print(
                    f"{Colors.YELLOW}No resource directory found: {resource_dir.name}{Colors.RESET}",
                    file=sys.stderr,
                )

            print("</document>")

    # Handle missing files
    if missing_files:
        print(
            f"{Colors.RED}Error: The following files do not exist:{Colors.RESET}",
            file=sys.stderr,
        )
        for f in missing_files:
            print(f"  {f}", file=sys.stderr)
        print(
            f"{Colors.YELLOW}Suggestion: Check file paths and ensure files exist{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


def list_links(
    input_files: list[Path],
    verbose: bool = False,
    quiet: bool = False,
    dry_run: bool = False,
) -> None:
    """List all unique URLs found in the input files."""
    all_urls = set()
    missing_files = []

    # Collect all URLs from all files
    for file_path in input_files:
        if not file_path.exists():
            missing_files.append(file_path)
            continue

        if verbose and not quiet:
            print(
                f"{Colors.CYAN}Scanning {file_path.name}...{Colors.RESET}",
                file=sys.stderr,
            )

        try:
            content = read_file(file_path)
            urls = extract_urls(content)
            all_urls.update(urls)

            if verbose and urls and not quiet:
                print(
                    f"{Colors.GREEN}Found {len(urls)} URLs in {file_path.name}{Colors.RESET}",
                    file=sys.stderr,
                )
        except FileNotFoundError:
            print(
                f"{Colors.RED}Error: File not found: {file_path}{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Check the file path and ensure the file exists{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except PermissionError:
            print(
                f"{Colors.RED}Error: Permission denied reading {file_path}{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Check file permissions or run with appropriate privileges{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except UnicodeDecodeError:
            print(
                f"{Colors.RED}Error: Unable to decode {file_path} as UTF-8{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Convert the file to UTF-8 encoding{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(
                f"{Colors.RED}Error reading {file_path}: {e}{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Check if the file is corrupted or try again{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Handle missing files
    if missing_files:
        print(
            f"{Colors.RED}Error: The following files do not exist:{Colors.RESET}",
            file=sys.stderr,
        )
        for f in missing_files:
            print(f"  {f}", file=sys.stderr)
        print(
            f"{Colors.YELLOW}Suggestion: Check file paths and ensure files exist{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Output the deduplicated URLs
    if not all_urls:
        print(
            f"{Colors.YELLOW}No URLs found in any files.{Colors.RESET}", file=sys.stderr
        )
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
    else:
        for url in sorted(all_urls):
            print(url)


def process_files(
    input_files: list[Path],
    exec_cmd: str | None = None,
    verbose: bool = False,
    max_retries: int = 3,
    quiet: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Process input files and save URL content to resource folders.

    Args:
        input_files: List of input markdown files to process
        exec_cmd: Optional command to process content before saving
        verbose: Enable verbose output
        max_retries: Maximum number of retry attempts for failed fetches (default: 3)
        quiet: Minimize output
        dry_run: Show what would be done without actually doing it
        force: Force redownload even if file already exists
    """
    all_urls = set()
    missing_files = []

    # First pass: collect all URLs from all files
    for file_path in input_files:
        if not file_path.exists():
            missing_files.append(file_path)
            continue

        if not quiet:
            print(
                f"{Colors.CYAN}Extracting URLs from {file_path.name}...{Colors.RESET}"
            )
        try:
            content = read_file(file_path)
            urls = extract_urls(content)
            all_urls.update(urls)

            if urls and not quiet:
                print(
                    f"{Colors.GREEN}Found {len(urls)} URLs in {file_path.name}{Colors.RESET}"
                )
            elif verbose and not quiet:
                print(f"{Colors.YELLOW}No URLs found in {file_path.name}{Colors.RESET}")
        except FileNotFoundError:
            print(
                f"{Colors.RED}Error: File not found: {file_path}{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Check the file path and ensure the file exists{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except PermissionError:
            print(
                f"{Colors.RED}Error: Permission denied reading {file_path}{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Check file permissions or run with appropriate privileges{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except UnicodeDecodeError:
            print(
                f"{Colors.RED}Error: Unable to decode {file_path} as UTF-8{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Convert the file to UTF-8 encoding{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(
                f"{Colors.RED}Error reading {file_path}: {e}{Colors.RESET}",
                file=sys.stderr,
            )
            print(
                f"{Colors.YELLOW}Suggestion: Check if the file is corrupted or try again{Colors.RESET}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Handle missing files
    if missing_files:
        print(
            f"{Colors.RED}Error: The following files do not exist:{Colors.RESET}",
            file=sys.stderr,
        )
        for f in missing_files:
            print(f"  {f}", file=sys.stderr)
        print(
            f"{Colors.YELLOW}Suggestion: Check file paths and ensure files exist{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Remove duplicates and show total
    if not all_urls:
        print(f"{Colors.YELLOW}No URLs found in any files.{Colors.RESET}")
        return

    if not quiet:
        print(f"\n{Colors.BOLD}Total unique URLs found: {len(all_urls)}{Colors.RESET}")

    # Process each input file
    for file_path in input_files:
        # Create resource folder for this file
        resource_dir = file_path.parent / f"{file_path.stem}-resources"
        if not dry_run:
            try:
                resource_dir.mkdir(exist_ok=True)
            except PermissionError:
                print(
                    f"{Colors.RED}Error: Permission denied creating directory {resource_dir}{Colors.RESET}",
                    file=sys.stderr,
                )
                print(
                    f"{Colors.YELLOW}Suggestion: Check directory permissions or run with appropriate privileges{Colors.RESET}",
                    file=sys.stderr,
                )
                sys.exit(1)
            except OSError as e:
                print(
                    f"{Colors.RED}Error: Cannot create directory {resource_dir}: {e}{Colors.RESET}",
                    file=sys.stderr,
                )
                print(
                    f"{Colors.YELLOW}Suggestion: Check disk space and file system permissions{Colors.RESET}",
                    file=sys.stderr,
                )
                sys.exit(1)

        if not quiet:
            if dry_run:
                print(
                    f"\n{Colors.MAGENTA}Would create and process {file_path.name} -> {resource_dir.name}/{Colors.RESET}"
                )
            else:
                print(
                    f"\n{Colors.MAGENTA}Processing {file_path.name} -> {resource_dir.name}/{Colors.RESET}"
                )

        # Get URLs from this specific file
        content = read_file(file_path)
        file_urls = extract_urls(content)

        if file_urls:
            fetch_and_save_urls(
                file_urls,
                resource_dir,
                exec_cmd,
                verbose,
                max_retries,
                quiet,
                dry_run,
                force,
            )
        else:
            if not quiet:
                print(f"{Colors.YELLOW}No URLs to process for this file.{Colors.RESET}")


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract URLs from markdown files and save each link as individual markdown files in resource folders.\n"
        "By default, existing files are skipped to save time and bandwidth.",
        epilog="Examples:\n"
        "  linkweaver notes.md                      # Process file, skip existing resources\n"
        "  linkweaver --force notes.md              # Force redownload all resources\n"
        "  linkweaver --list-links notes.md         # List all URLs found\n"
        "  linkweaver --xml-cat notes.md            # Concatenate with resources\n"
        "  linkweaver -x 'llm -t clean' notes.md    # Process with custom command\n"
        "  linkweaver --retries 5 notes.md          # Use 5 retry attempts for failed URLs\n"
        "  linkweaver --quiet --dry-run notes.md    # Preview actions quietly\n"
        "  linkweaver -q -v notes.md                # Quiet mode overrides verbose\n"
        "  linkweaver --no-color notes.md           # Disable colored output\n"
        "\n"
        "Common workflows:\n"
        "  linkweaver --list-links *.md | head -10  # Preview first 10 URLs\n"
        "  linkweaver --dry-run notes.md            # See what would be fetched/skipped\n"
        "  linkweaver --force --dry-run notes.md    # Preview forced redownload\n"
        "  linkweaver --retries 0 notes.md          # Disable retries for speed\n"
        "  linkweaver --xml-cat notes.md | less     # Browse concatenated content",
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
        help="List all unique URLs found in the files (no downloading)",
    )

    parser.add_argument(
        "--xml-cat",
        action="store_true",
        help="Concatenate files with their resource folders in XML structure",
    )

    parser.add_argument(
        "-x",
        "--exec",
        dest="exec_cmd",
        metavar="COMMAND",
        help="Execute a shell command on the markdown output before saving (e.g., 'llm -t mdclean')",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed progress information",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Number of retry attempts for failed URL fetches (default: 3)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimize output (opposite of verbose, but still show errors/warnings)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
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
        help="Force redownload of files even if they already exist",
    )

    args = parser.parse_args()

    # Validate retries parameter
    if args.retries < 0:
        print(
            f"{Colors.RED}Error: --retries must be a non-negative integer{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Handle color output
    if args.no_color or os.environ.get("NO_COLOR"):
        Colors.disable()

    # Show help if no input files provided
    if not args.input_files:
        parser.print_help()
        sys.exit(0)

    try:
        if args.list_links:
            list_links(args.input_files, args.verbose, args.quiet, args.dry_run)
        elif args.xml_cat:
            xml_cat_files(args.input_files, args.verbose, args.quiet, args.dry_run)
        else:
            process_files(
                args.input_files,
                args.exec_cmd,
                args.verbose,
                args.retries,
                args.quiet,
                args.dry_run,
                args.force,
            )
    except KeyboardInterrupt:
        print(
            f"\n{Colors.YELLOW}Operation cancelled by user{Colors.RESET}",
            file=sys.stderr,
        )
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.RESET}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
