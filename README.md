# Link Weaver 🕸️

Extract URLs from markdown files and process them with three powerful modes: save as organized resource folders, list all links, or concatenate with resources in XML format!

## ✨ Features

- 📝 **Markdown URL Extraction**: Finds and extracts all URLs from your markdown files automatically
- 🌐 **Multi-format Support**: Handles web pages, PDFs, YouTube videos, and more thanks to [MarkItDown](https://github.com/microsoft/markitdown)
- 📁 **Resource Mode**: Creates resource folders with each link saved as individual markdown files
- 📋 **List Mode**: Quickly list all unique URLs found across files
- 🔗 **XML Cat Mode**: Concatenate files with their resources in structured XML format
- 🏷️ **Smart Naming**: Uses URL-based filenames that are human-readable and identifiable
- ⚡ **Duplicate Removal**: Automatically removes duplicate URLs before processing
- 📊 **Progress Tracking**: Shows real-time progress with clear status indicators
- 💻 **CLI Interface**: Simple command-line interface for easy integration into workflows

## 📦 Installation

```bash
# Install from PyPI (when available)
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
```

## 🔧 CLI API

### Basic Usage

```bash
$ linkweaver --help
usage: linkweaver [-h] [--list-links] [--xml-cat] input_files [input_files ...]

Extract URLs from markdown files and save each link as individual markdown files in resource folders

positional arguments:
  input_files           One or more markdown files to process

options:
  -h, --help            show this help message and exit
  --list-links, -l      List all unique URLs found in the files (no downloading)
  --xml-cat             Concatenate all markdown files with their resource folders in XML structure
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

## 🔄 Workflow Example

### Default Mode (Resource Creation)
```bash
$ linkweaver research-notes.md
Extracting URLs from research-notes.md...
Found 5 URLs in research-notes.md

Total unique URLs found: 5

Processing research-notes.md -> research-notes-resources/
Processing 5 unique URLs using markitdown...
Fetching 1/5: https://example.com/article
✓ Saved: example.com-article.md
Fetching 2/5: https://github.com/user/repo
✓ Saved: github.com-user-repo.md
...
```

### List Links Mode
```bash
$ linkweaver --list-links research-notes.md
https://example.com/article
https://github.com/user/repo
https://youtube.com/watch?v=abc123
...
```

### XML Cat Mode
```bash
$ linkweaver --xml-cat research-notes.md
<document source='research-notes.md'>
[Original file content]

<resources>
<resource file='example.com-article.md'>
[Resource content]
</resource>
...
</resources>
</document>
```

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.
