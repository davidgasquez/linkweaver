import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import linkweaver


class FakeMarkItDown:
    def __init__(self, enable_builtins: bool) -> None:
        self.enable_builtins = enable_builtins

    def convert(self, url: str) -> SimpleNamespace:
        return SimpleNamespace(title="Fetched", markdown=f"content from {url}")


class EmptyMarkItDown:
    def __init__(self, enable_builtins: bool) -> None:
        self.enable_builtins = enable_builtins

    def convert(self, url: str) -> SimpleNamespace:
        return SimpleNamespace(title="Empty", markdown="")


class FailingMarkItDown:
    def __init__(self, enable_builtins: bool) -> None:
        raise AssertionError("MarkItDown should not be used for plaintext URLs")


class FakeHeaders:
    def __init__(self, content_type: str = "text/plain") -> None:
        self.content_type = content_type

    def get_content_type(self) -> str:
        return self.content_type

    def get_content_charset(self) -> str | None:
        return None


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "text/plain") -> None:
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class LinkWeaverTests(unittest.TestCase):
    def test_extract_urls_preserves_balanced_parentheses(self) -> None:
        content = "\n".join(
            [
                "[Example](https://example.com/a(b))",
                '[Title](https://example.com/titled "Example title")',
                "bare https://example.com/path). next",
                "nested https://example.com/a(b).",
            ]
        )

        self.assertEqual(
            linkweaver.extract_urls(content),
            {
                "https://example.com/a(b)",
                "https://example.com/path",
                "https://example.com/titled",
            },
        )

    def test_url_to_filename_avoids_double_markdown_extension(self) -> None:
        self.assertEqual(
            linkweaver.url_to_filename(
                "https://raw.githubusercontent.com/org/repo/main/notes.md"
            ),
            "raw-githubusercontent-com-org-repo-main-notes.md",
        )
        self.assertEqual(
            linkweaver.url_to_filename("https://example.com/paper.pdf"),
            "example-com-paper.pdf.md",
        )

    def test_plaintext_url_detection_ignores_query_string(self) -> None:
        self.assertTrue(
            linkweaver._is_plaintext_url("https://example.com/llms-full.txt?x=1")
        )
        self.assertTrue(
            linkweaver._is_plaintext_url("https://example.com/docs/readme.MD")
        )
        self.assertFalse(linkweaver._is_plaintext_url("https://example.com/file.pdf"))

    def test_process_dry_run_does_not_create_resource_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "notes.md"
            note.write_text("https://example.com/a\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                linkweaver.process_files([note], dry_run=True)

            self.assertFalse((Path(tmp) / "notes-resources").exists())

    def test_process_uses_custom_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "notes.md"
            output_dir = root / "custom" / "resources"
            note.write_text("https://example.com/a\n", encoding="utf-8")

            with patch.object(linkweaver, "MarkItDown", FakeMarkItDown):
                with contextlib.redirect_stdout(io.StringIO()):
                    linkweaver.process_files(
                        [note],
                        max_retries=0,
                        output_dir=output_dir,
                    )

            self.assertTrue((output_dir / "example-com-a.md").exists())
            self.assertFalse((root / "notes-resources").exists())

    def test_empty_conversion_writes_error_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            with patch.object(linkweaver, "MarkItDown", EmptyMarkItDown):
                with contextlib.redirect_stdout(io.StringIO()):
                    linkweaver.fetch_and_save_urls(
                        {"https://example.com/empty"},
                        output_dir,
                        max_retries=0,
                    )

            error_file = output_dir / "example-com-empty.md"
            self.assertTrue(error_file.exists())
            content = error_file.read_text(encoding="utf-8")
            self.assertIn("converted markdown content is empty", content)

    def test_plaintext_fetch_saves_raw_content_without_markitdown(self) -> None:
        def fake_urlopen(url_request: object, timeout: int) -> FakeResponse:
            self.assertEqual(timeout, 30)
            return FakeResponse(b"# Karma\n\nRaw llms text\n")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            with patch.object(linkweaver, "MarkItDown", FailingMarkItDown):
                with patch.object(linkweaver.request, "urlopen", fake_urlopen):
                    with contextlib.redirect_stdout(io.StringIO()):
                        linkweaver.fetch_and_save_urls(
                            {"https://www.karmahq.xyz/llms-full.txt"},
                            output_dir,
                            max_retries=0,
                        )

            content = (output_dir / "www-karmahq-xyz-llms-full.txt.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(content, "# Karma\n\nRaw llms text\n")

    def test_plaintext_extension_with_html_response_falls_back_to_markitdown(
        self,
    ) -> None:
        def fake_urlopen(url_request: object, timeout: int) -> FakeResponse:
            self.assertEqual(timeout, 30)
            return FakeResponse(b"<html></html>", content_type="text/html")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            with patch.object(linkweaver, "MarkItDown", FakeMarkItDown):
                with patch.object(linkweaver.request, "urlopen", fake_urlopen):
                    with contextlib.redirect_stdout(io.StringIO()):
                        linkweaver.fetch_and_save_urls(
                            {"https://github.com/org/repo/blob/main/readme.md"},
                            output_dir,
                            max_retries=0,
                        )

            content = (
                output_dir / "github-com-org-repo-blob-main-readme.md"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "**Source:** https://github.com/org/repo/blob/main/readme.md", content
            )
            self.assertIn(
                "content from https://github.com/org/repo/blob/main/readme.md", content
            )

    def test_help_omits_removed_shell_options(self) -> None:
        stdout = io.StringIO()

        with patch.object(sys, "argv", ["linkweaver", "--help"]):
            with contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as exit_context:
                    linkweaver.cli()

        self.assertEqual(exit_context.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertNotIn("--xml-cat", help_text)
        self.assertNotIn("--exec", help_text)


if __name__ == "__main__":
    unittest.main()
