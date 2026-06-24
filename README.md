# LinkWeaver 🕸️

LinkWeaver finds URLs in Markdown files and uses [MarkItDown](https://github.com/microsoft/markitdown) to turn the URL content into a local Markdown file.

## 📦 Install

Use `uvx` if you only want to run LinkWeaver once.

```bash
uvx linkweaver notes.md
```

If you use `uv tools`, install LinkWeaver once and run it from anywhere.

```bash
uv tool install linkweaver
```

You can also install the package from PyPI.

```bash
pip install linkweaver
```

## 🚀 Quick start

Process one file.

```bash
linkweaver notes.md
```

When you run this command, LinkWeaver creates a `notes-resources/` folder next to `notes.md`. LinkWeaver saves one `.md` file in that folder for each URL.

Run it with `uvx` without installing anything too!

```bash
uvx linkweaver notes.md
```

List all unique URLs in your files.

```bash
linkweaver --list-links notes/*.md
```

Save all resource files to one folder.

```bash
linkweaver -o resources notes.md
```

Download files again even when they already exist.

```bash
linkweaver --force notes.md
```

Preview the work without writing files or fetching URLs.

```bash
linkweaver --dry-run notes.md
```

## 🧰 Common tasks

Preview the first 10 URLs across Markdown files.

```bash
linkweaver --list-links *.md | head -10
```

See which URLs LinkWeaver would fetch or skip.

```bash
linkweaver --dry-run notes.md
```

Preview a run that would download existing files again.

```bash
linkweaver --force --dry-run notes.md
```

Turn off retries.

```bash
linkweaver --retries 0 notes.md
```

Run with less output and 5 retries.

```bash
linkweaver --quiet --retries 5 notes.md
```

Process several files.

```bash
linkweaver *.md
```

## 📁 Output files

For each input file, LinkWeaver creates a resource folder. When you process `notes.md`, you get this folder.

```text
notes.md
notes-resources/
├── example.com-page-title.md
├── github.com-user-repo.md
└── youtube.com-watch-v-abc123.md
```

Use `-o DIR` or `--output-dir DIR` to put all resource files in one folder.

In each resource file, you get:

* The file name is based on the URL.
* You can see the source URL.
* You can read the content as Markdown.
* You can see error details if the download failed.

A resource file looks like this.

```markdown
# Example Page Title

**Source:** https://example.com/page/title

[Converted markdown content here...]
```

## 📜 License

MIT. See [LICENSE](LICENSE).
