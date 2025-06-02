import argparse
import re
import sys
from pathlib import Path

from markitdown import MarkItDown


def read_file(file_path: Path) -> str:
    """Read content from a file."""
    return file_path.read_text(encoding="utf-8")


def extract_urls(content: str) -> set[str]:
    """Extract all URLs from markdown content."""
    urls = set()

    # Pattern for markdown links: [text](url)
    markdown_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
    for _, url in markdown_links:
        urls.add(url.strip())

    # Pattern for bare URLs (http/https)
    bare_urls = re.findall(r"https?://[^\s\)]+", content)
    for url in bare_urls:
        # Clean up any trailing punctuation
        url = url.rstrip(".,;:!?)")
        urls.add(url)

    return urls


def wrap_content(content: str, filename: str) -> str:
    """Wrap content in main-note XML tags with filename."""
    return f'<main-note source="{filename}">\n{content}\n</main-note>'


def fetch_url_content(urls: set[str]) -> list[str]:
    """Fetch content from URLs and return wrapped content."""
    if not urls:
        return []

    md = MarkItDown(enable_builtins=True)
    url_contents = []

    for url in sorted(urls):
        try:
            result = md.convert(url)
            title = result.title or "Untitled"
            content = result.markdown or ""

            wrapped_content = f'<url-content source="{url}" title="{title}">\n{content}\n</url-content>'
            url_contents.append(wrapped_content)

        except Exception as e:
            print(f"Warning: Failed to fetch {url}: {e}", file=sys.stderr)
            # Still create a tag for failed URLs
            wrapped_content = f'<url-content source="{url}" title="Failed to fetch">\nError: {str(e)}\n</url-content>'
            url_contents.append(wrapped_content)

    return url_contents


def process_files(input_files: list[Path], output_file: Path | None = None) -> None:
    """Process input files and output wrapped content with URL tags."""
    all_content = []
    all_urls = set()

    for file_path in input_files:
        if not file_path.exists():
            print(f"Error: File {file_path} does not exist", file=sys.stderr)
            sys.exit(1)

        content = read_file(file_path)
        wrapped_content = wrap_content(content, file_path.name)
        all_content.append(wrapped_content)

        # Extract URLs from this file
        urls = extract_urls(content)
        all_urls.update(urls)

    # Fetch URL content
    output_parts = all_content
    if all_urls:
        url_contents = fetch_url_content(all_urls)
        output_parts.extend(url_contents)

    output = "\n".join(output_parts)

    if output_file:
        _ = output_file.write_text(output, encoding="utf-8")
        print(f"Output written to {output_file}")
    else:
        print(output)


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract URLs from markdown files and fetch their content into a consolidated document"
    )
    _ = parser.add_argument(
        "input_files",
        nargs="+",
        type=Path,
        help="One or more markdown files to process",
    )
    _ = parser.add_argument(
        "--output", "-o", type=Path, help="Output file path (default: stdout)"
    )

    args = parser.parse_args()
    process_files(args.input_files, args.output)


if __name__ == "__main__":
    cli()
