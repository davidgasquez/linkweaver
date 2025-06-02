# Link Weaver 🕸️

Extract URLs from markdown files and fetch their content into a consolidated document. Useful for feeding your notes to LLMs!

## ✨ Features

- 📝 **Markdown URL Extraction**: Automatically finds all URLs in your markdown documents
- 🌐 **Multi-format Support**: Handles web pages, PDFs, YouTube videos, and more thanks to [MarkItDown](https://github.com/microsoft/markitdown)
- 📋 **Consolidated Output**: Creates a single document with your notes + all external content
- 🏷️ **Clear Separation**: Uses XML-style tags to distinguish between original notes and fetched content
- 💻 **CLI Interface**: Simple command-line interface for easy integration into workflows

## 📦 Installation

```bash
pip install linkweaver
```

## 🚀 Quick Start

```bash
# Process a single markdown file
lw my-notes.md

# Process with custom output
lw my-notes.md --output consolidated-notes.md

# Process multiple files
lw notes/*.md --output research-compilation.md
```

## 🔧 CLI API

### Basic Usage

```bash
$ lw --help
usage: lw [-h] [--output OUTPUT] input_files [input_files ...]

Extract URLs from markdown files and fetch their content into a consolidated document

positional arguments:
  input_files          One or more markdown files to process

options:
  -h, --help           show this help message and exit
  --output, -o OUTPUT  Output file path (default: stdout)
```

## 📄 Output Format

The output includes your original markdown content with fetched URL content clearly marked:

```markdown
<main-note source="my-notes.md">
# Your Original Note Title

Your original markdown content here with [links](https://example.com).
</main-note>
<url-content source="https://example.com" title="Example Page">
# Example Page Content

The markdown-converted content from the URL appears here...
</url-content>
<url-content source="https://another-link.com" title="Another Page">
# Another Page Content

More fetched content...
</url-content>
```

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.
