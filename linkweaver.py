import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

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


def url_to_filename(url: str) -> str:
    """Convert URL to a clean filename."""
    parsed = urlparse(url)

    # Start with domain
    filename = parsed.netloc or "unknown-domain"

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


def fetch_and_save_urls(urls: set[str], output_dir: Path) -> None:
    """Fetch content from URLs and save each as individual markdown files."""
    if not urls:
        print("No URLs found to process.")
        return

    md = MarkItDown(enable_builtins=True)

    sorted_urls = sorted(urls)
    total = len(sorted_urls)

    print(f"Processing {total} unique URLs using markitdown...")

    for i, url in enumerate(sorted_urls, 1):
        filename = url_to_filename(url)
        output_path = output_dir / filename

        print(f"Fetching {i}/{total}: {url}")

        try:
            result = md.convert(url)
            title = result.title or "Untitled"
            content = result.markdown or ""

            # Add metadata header to the markdown file
            full_content = f"# {title}\n\n**Source:** {url}\n\n{content}"

            output_path.write_text(full_content, encoding="utf-8")
            print(f"✓ Saved: {filename}")

        except Exception as e:
            print(f"✗ Failed: {url} - {e}")
            # Still create a file with error info
            error_content = (
                f"# Failed to fetch content\n\n**Source:** {url}\n\n**Error:** {str(e)}"
            )
            output_path.write_text(error_content, encoding="utf-8")
            print(f"✓ Error logged: {filename}")


def xml_cat_files(input_files: list[Path]) -> None:
    """Concatenate input files and their resource folders in XML structure."""
    for file_path in input_files:
        if not file_path.exists():
            print(f"Error: File {file_path} does not exist", file=sys.stderr)
            sys.exit(1)

        # Get the corresponding resource folder
        resource_dir = file_path.parent / f"{file_path.stem}-resources"

        # Start with the original file
        print(f"<document source='{file_path.name}'>")
        try:
            original_content = read_file(file_path)
            print(original_content)
        except Exception as e:
            print(f"Error reading {file_path.name}: {e}", file=sys.stderr)

        # Add resource files if they exist
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
                    except Exception as e:
                        print(f"Error reading {md_file.name}: {e}", file=sys.stderr)
                    print("</resource>")
                print("\n</resources>")

        print("</document>")


def list_links(input_files: list[Path]) -> None:
    """List all unique URLs found in the input files."""
    all_urls = set()

    # Collect all URLs from all files
    for file_path in input_files:
        if not file_path.exists():
            print(f"Error: File {file_path} does not exist", file=sys.stderr)
            sys.exit(1)

        content = read_file(file_path)
        urls = extract_urls(content)
        all_urls.update(urls)

    # Output the deduplicated URLs
    if not all_urls:
        print("No URLs found in any files.")
        return

    for url in sorted(all_urls):
        print(url)


def process_files(input_files: list[Path]) -> None:
    """Process input files and save URL content to resource folders."""
    all_urls = set()

    # First pass: collect all URLs from all files
    for file_path in input_files:
        if not file_path.exists():
            print(f"Error: File {file_path} does not exist", file=sys.stderr)
            sys.exit(1)

        print(f"Extracting URLs from {file_path.name}...")
        content = read_file(file_path)
        urls = extract_urls(content)
        all_urls.update(urls)

        if urls:
            print(f"Found {len(urls)} URLs in {file_path.name}")

    # Remove duplicates and show total
    if not all_urls:
        print("No URLs found in any files.")
        return

    print(f"\nTotal unique URLs found: {len(all_urls)}")

    # Process each input file
    for file_path in input_files:
        # Create resource folder for this file
        resource_dir = file_path.parent / f"{file_path.stem}-resources"
        resource_dir.mkdir(exist_ok=True)

        print(f"\nProcessing {file_path.name} -> {resource_dir.name}/")

        # Get URLs from this specific file
        content = read_file(file_path)
        file_urls = extract_urls(content)

        if file_urls:
            fetch_and_save_urls(file_urls, resource_dir)
        else:
            print("No URLs to process for this file.")


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract URLs from markdown files and save each link as individual markdown files in resource folders"
    )
    _ = parser.add_argument(
        "input_files",
        nargs="+",
        type=Path,
        help="One or more markdown files to process",
    )
    _ = parser.add_argument(
        "--list-links",
        "-l",
        action="store_true",
        help="List all unique URLs found in the files (no downloading)",
    )
    _ = parser.add_argument(
        "--xml-cat",
        action="store_true",
        help="Concatenate all markdown files in the specified folder(s)",
    )

    args = parser.parse_args()

    if args.list_links:
        list_links(args.input_files)
    elif args.xml_cat:
        xml_cat_files(args.input_files)
    else:
        process_files(args.input_files)


if __name__ == "__main__":
    cli()
