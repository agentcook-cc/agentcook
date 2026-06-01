"""Unit tests for agentcook_core.media module."""

from __future__ import annotations

import pytest

from agentcook_core.media import (
    FileRenderer,
    ImageRenderer,
    MarkdownRenderer,
    MediaAttachment,
    MediaError,
    MediaProcessor,
    MediaRegistry,
    MediaType,
    MermaidRenderer,
    ProcessedMedia,
)


# ---------------------------------------------------------------------------
# MediaType Tests
# ---------------------------------------------------------------------------


class TestMediaType:
    def test_all_types(self):
        expected = {"text", "image", "pdf", "markdown", "mermaid", "file"}
        assert {t.value for t in MediaType} == expected

    def test_string_enum(self):
        assert MediaType.MARKDOWN == "markdown"


# ---------------------------------------------------------------------------
# MediaAttachment Tests
# ---------------------------------------------------------------------------


class TestMediaAttachment:
    def test_frozen(self):
        a = MediaAttachment(media_type=MediaType.TEXT, content="hi")
        with pytest.raises(AttributeError):
            a.content = "other"  # type: ignore[misc]

    def test_defaults(self):
        a = MediaAttachment(media_type=MediaType.IMAGE)
        assert a.url == ""
        assert a.mime_type == ""
        assert a.size_bytes == 0
        assert a.content == ""
        assert a.filename == ""
        assert a.metadata == {}


# ---------------------------------------------------------------------------
# MarkdownRenderer Tests
# ---------------------------------------------------------------------------


class TestMarkdownRenderer:
    def test_protocol_compliance(self):
        assert isinstance(MarkdownRenderer(), MediaProcessor)

    def test_supported_type(self):
        assert MarkdownRenderer().supported_type == MediaType.MARKDOWN

    def test_renders_headers(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="# Hello\n## World")
        result = r.process(att)
        assert "<h1>" in result.rendered_html
        assert "<h2>" in result.rendered_html

    def test_renders_bold(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="**bold**")
        result = r.process(att)
        assert "<strong>bold</strong>" in result.rendered_html

    def test_renders_code_block(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="```python\nprint(1)\n```")
        result = r.process(att)
        assert '<pre><code class="language-python">' in result.rendered_html

    def test_renders_inline_code(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="use `foo` here")
        result = r.process(att)
        assert "<code>foo</code>" in result.rendered_html

    def test_renders_links(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="[click](http://x.com)")
        result = r.process(att)
        assert 'href="http://x.com"' in result.rendered_html

    def test_plain_text_fallback(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="just text")
        result = r.process(att)
        assert result.rendered_text == "just text"

    def test_empty_content_with_url(self):
        r = MarkdownRenderer()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, url="/file.md", filename="notes.md")
        result = r.process(att)
        assert "notes.md" in result.rendered_html


# ---------------------------------------------------------------------------
# MermaidRenderer Tests
# ---------------------------------------------------------------------------


class TestMermaidRenderer:
    def test_protocol_compliance(self):
        assert isinstance(MermaidRenderer(), MediaProcessor)

    def test_supported_type(self):
        assert MermaidRenderer().supported_type == MediaType.MERMAID

    def test_renders_svg_placeholder(self):
        r = MermaidRenderer()
        att = MediaAttachment(media_type=MediaType.MERMAID, content="graph TD\nA-->B")
        result = r.process(att)
        assert "<svg" in result.svg
        assert "mermaid-placeholder" in result.svg

    def test_rendered_html_has_mermaid_class(self):
        r = MermaidRenderer()
        att = MediaAttachment(media_type=MediaType.MERMAID, content="graph LR\nX-->Y")
        result = r.process(att)
        assert 'class="mermaid"' in result.rendered_html

    def test_detects_flowchart(self):
        r = MermaidRenderer()
        att = MediaAttachment(media_type=MediaType.MERMAID, content="graph TD\nA-->B")
        result = r.process(att)
        assert result.metadata["diagram_type"] == "flowchart"

    def test_empty_content_raises(self):
        r = MermaidRenderer()
        att = MediaAttachment(media_type=MediaType.MERMAID, content="")
        with pytest.raises(MediaError):
            r.process(att)


# ---------------------------------------------------------------------------
# ImageRenderer Tests
# ---------------------------------------------------------------------------


class TestImageRenderer:
    def test_protocol_compliance(self):
        assert isinstance(ImageRenderer(), MediaProcessor)

    def test_renders_img_tag(self):
        r = ImageRenderer()
        att = MediaAttachment(media_type=MediaType.IMAGE, url="http://img.png", filename="cat.png")
        result = r.process(att)
        assert "<img" in result.rendered_html
        assert 'src="http://img.png"' in result.rendered_html

    def test_alt_from_metadata(self):
        r = ImageRenderer()
        att = MediaAttachment(media_type=MediaType.IMAGE, url="x.png", metadata={"alt": "A cat"})
        result = r.process(att)
        assert 'alt="A cat"' in result.rendered_html

    def test_text_fallback(self):
        r = ImageRenderer()
        att = MediaAttachment(media_type=MediaType.IMAGE, url="x.png", filename="dog.jpg")
        result = r.process(att)
        assert "[Image: dog.jpg]" == result.rendered_text


# ---------------------------------------------------------------------------
# FileRenderer Tests
# ---------------------------------------------------------------------------


class TestFileRenderer:
    def test_protocol_compliance(self):
        assert isinstance(FileRenderer(), MediaProcessor)

    def test_renders_download_card(self):
        r = FileRenderer()
        att = MediaAttachment(media_type=MediaType.FILE, url="/f.zip", filename="data.zip", size_bytes=2048)
        result = r.process(att)
        assert "file-card" in result.rendered_html
        assert "data.zip" in result.rendered_html
        assert "download" in result.rendered_html

    def test_size_formatting(self):
        r = FileRenderer()
        assert "1024 B" in r._format_size(1024) or "KB" in r._format_size(1024)

    def test_text_fallback(self):
        r = FileRenderer()
        att = MediaAttachment(media_type=MediaType.FILE, filename="report.pdf", size_bytes=1048576)
        result = r.process(att)
        assert "[File:" in result.rendered_text


# ---------------------------------------------------------------------------
# MediaRegistry Tests
# ---------------------------------------------------------------------------


class TestMediaRegistry:
    def test_default_registrations(self):
        reg = MediaRegistry()
        assert reg.supports(MediaType.MARKDOWN)
        assert reg.supports(MediaType.MERMAID)
        assert reg.supports(MediaType.IMAGE)
        assert reg.supports(MediaType.FILE)

    def test_unsupported_type_fallback(self):
        reg = MediaRegistry()
        att = MediaAttachment(media_type=MediaType.PDF, content="pdf bytes")
        result = reg.process(att)
        assert "Unsupported" in result.rendered_text

    def test_process_dispatches_correctly(self):
        reg = MediaRegistry()
        att = MediaAttachment(media_type=MediaType.MARKDOWN, content="**hi**")
        result = reg.process(att)
        assert "<strong>hi</strong>" in result.rendered_html

    def test_supported_types_list(self):
        reg = MediaRegistry()
        types = reg.supported_types
        assert MediaType.MARKDOWN in types
        assert len(types) >= 4

    def test_custom_processor_registration(self):
        class PdfProcessor:
            @property
            def supported_type(self):
                return MediaType.PDF

            def process(self, attachment):
                return ProcessedMedia(original=attachment, rendered_text="PDF rendered")

        reg = MediaRegistry()
        reg.register(PdfProcessor())
        assert reg.supports(MediaType.PDF)
        att = MediaAttachment(media_type=MediaType.PDF)
        assert reg.process(att).rendered_text == "PDF rendered"
