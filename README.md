# LinkWeaver 🕸️

Extract URLs from markdown files and convert them to individual markdown documents. LinkWeaver is a CLI tool that finds all URLs in your markdown files, fetches their content, converts to markdown, and saves each as a separate file in organized resource folders.

## ✨ Features

- 📝 **Markdown URL Extraction**: Finds and extracts all URLs from your markdown files automatically
- 🌐 **Multi-format Support**: Handles web pages, PDFs, YouTube videos, and more thanks to [MarkItDown](https://github.com/microsoft/markitdown)
- 📁 **Resource Mode**: Creates resource folders with each link saved as individual markdown files
- 📋 **List Mode**: Quickly list all unique URLs found across files
- 🔗 **XML Cat Mode**: Concatenate files with their resources in structured XML format
- 🏷️ **Smart Naming**: Uses URL-based filenames that are human-readable and identifiable
- ⚡ **Duplicate Removal**: Automatically removes duplicate URLs before processing
- 📊 **Progress Tracking**: Shows real-time progress with clear status indicators
- 🔄 **Retry Logic**: Automatic retry with exponential backoff for failed requests
- 🛠️ **Post-processing**: Execute custom commands on content before saving
- 💻 **CLI Interface**: Simple command-line interface for easy integration into workflows

## 📦 Installation

```bash
# Install as a tool with uv (recommended)
uv tool install linkweaver

# Or install from PyPI
pip install linkweaver

# Or install from source
git clone https://github.com/davidgasquez/linkweaver
cd linkweaver
uv sync
```

## 🚀 Quick Start

```bash
# Process files and create resource folders (default mode)
linkweaver my-notes.md
# Creates: my-notes-resources/ folder with individual .md files

# List all unique URLs found in files
linkweaver --list-links notes/*.md

# Concatenate files with their resources in XML format
linkweaver --xml-cat my-notes.md

# Process with custom command (e.g., clean up content)
linkweaver -x 'llm -t clean' my-notes.md

# Force redownload all resources
linkweaver --force my-notes.md

# Preview what would be done (dry run)
linkweaver --dry-run my-notes.md
```

## 🔧 CLI Options

### Main Commands

```bash
linkweaver [OPTIONS] input_files...

Options:
  -h, --help            Show help message and exit
  --list-links, -l      List all unique URLs found in files (no downloading)
  --xml-cat             Concatenate files with their resources in XML structure
  -x, --exec COMMAND    Execute shell command on content before saving
  -v, --verbose         Enable verbose output with detailed progress
  --retries N           Number of retry attempts for failed fetches (default: 3)
  -q, --quiet           Minimize output (still shows errors/warnings)
  --dry-run             Show what would be done without actually doing it
  --no-color            Disable colored output
  -f, --force           Force redownload even if files already exist
```

### Common Usage Patterns

```bash
# Preview first 10 URLs across multiple files
linkweaver --list-links *.md | head -10

# See what would be fetched/skipped
linkweaver --dry-run notes.md

# Preview forced redownload
linkweaver --force --dry-run notes.md

# Disable retries for speed
linkweaver --retries 0 notes.md

# Browse concatenated content
linkweaver --xml-cat notes.md | less

# Quiet mode with custom retry count
linkweaver --quiet --retries 5 notes.md

# Process multiple files
linkweaver *.md
```

## 📁 Output Structure

For each input file, linkweaver creates a resource folder with individual markdown files:

```
my-notes.md
my-notes-resources/
├── example.com-page-title.md
├── github.com-user-repo.md
└── youtube.com-watch-v-abc123.md
```

Each resource file includes:
- Clean, URL-based filename
- Original source URL in metadata
- Full markdown-converted content
- Error information if fetch failed

**Example resource file content:**
```markdown
# Example Page Title

**Source:** https://example.com/page/title

[Converted markdown content here...]
```

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.
