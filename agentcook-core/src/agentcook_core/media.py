"""Rich media processing — typed attachments + renderer pipeline.

Provides a typed media system for agent messages that can carry images,
PDFs, Mermaid diagrams, Markdown content, and arbitrary files.

Design:
- stdlib-only for Protocol/types.
- ``MediaProcessor`` Protocol — injected renderer per media type.
- ``MediaRegistry`` dispatches processing to the right renderer.
- Built-in renderers: MarkdownRenderer, MermaidRenderer (SVG stub).
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value Types
# ---------------------------------------------------------------------------


class MediaType(str, Enum):
    """Supported rich media types in agent messages."""

    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    MARKDOWN = "markdown"
    MERMAID = "mermaid"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class MediaAttachment:
    """A rich media attachment on a message.

    Attributes:
        media_type: The kind of media.
        url: Resource URL (local path, http, or data URI).
        mime_type: MIME type string (e.g. "image/png").
        size_bytes: File size in bytes (0 if unknown).
        content: Inline content (for text/markdown/mermaid).
        filename: Original filename for downloads.
        metadata: Extra key-value pairs (alt text, dimensions, etc.).
    """

    media_type: MediaType
    url: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    content: str = ""
    filename: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProcessedMedia:
    """Result of processing a media attachment.

    Attributes:
        original: The source attachment.
        rendered_html: HTML representation for web display.
        rendered_text: Plain text fallback.
        svg: SVG output (for mermaid diagrams).
        metadata: Processing metadata (duration, warnings, etc.).
    """

    original: MediaAttachment
    rendered_html: str = ""
    rendered_text: str = ""
    svg: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MediaError(Exception):
    """Raised on media processing failures."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MediaProcessor(Protocol):
    """Processes a specific media type into rendered output."""

    @property
    def supported_type(self) -> MediaType:
        """The media type this processor handles."""
        ...

    def process(self, attachment: MediaAttachment) -> ProcessedMedia:
        """Render the attachment. Raises MediaError on failure."""
        ...


# ---------------------------------------------------------------------------
# Built-in Renderers
# ---------------------------------------------------------------------------


class MarkdownRenderer:
    """Renders Markdown content to HTML (basic subset, stdlib-only).

    Supports: headers, bold, italic, code blocks, inline code, links, lists.
    For production, swap with a proper Markdown library (markdown-it, etc.).
    """

    @property
    def supported_type(self) -> MediaType:
        return MediaType.MARKDOWN

    def process(self, attachment: MediaAttachment) -> ProcessedMedia:
        content = attachment.content or ""
        if not content and attachment.url:
            content = f"[Markdown file: {attachment.filename or attachment.url}]"

        rendered_html = self._render(content)
        return ProcessedMedia(
            original=attachment,
            rendered_html=rendered_html,
            rendered_text=content,
            metadata={"renderer": "stdlib_markdown", "input_length": len(content)},
        )

    def _render(self, text: str) -> str:
        """Basic Markdown → HTML conversion (stdlib-only subset)."""
        lines = text.split("\n")
        html_lines: list[str] = []
        in_code_block = False
        code_lang = ""

        for line in lines:
            if line.startswith("```"):
                if not in_code_block:
                    code_lang = line[3:].strip()
                    html_lines.append(f'<pre><code class="language-{html.escape(code_lang)}">')
                    in_code_block = True
                else:
                    html_lines.append("</code></pre>")
                    in_code_block = False
                continue

            if in_code_block:
                html_lines.append(html.escape(line))
                continue

            # Headers
            if line.startswith("### "):
                html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("# "):
                html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("- "):
                html_lines.append(f"<li>{self._inline(line[2:])}</li>")
            elif line.strip() == "":
                html_lines.append("")
            else:
                html_lines.append(f"<p>{self._inline(line)}</p>")

        return "\n".join(html_lines)

    def _inline(self, text: str) -> str:
        """Handle inline formatting: bold, italic, code, links."""
        escaped = html.escape(text)
        # Bold **text**
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        # Italic *text*
        escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
        # Inline code `text`
        escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
        # Links [text](url)
        escaped = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', escaped)
        return escaped


class MermaidRenderer:
    """Renders Mermaid diagram definitions to SVG placeholders.

    In production, this calls mermaid CLI or a rendering service.
    The stdlib-only version outputs a structured SVG placeholder
    that frontend can render client-side with mermaid.js.
    """

    @property
    def supported_type(self) -> MediaType:
        return MediaType.MERMAID

    def process(self, attachment: MediaAttachment) -> ProcessedMedia:
        content = attachment.content or ""
        if not content:
            raise MediaError("Mermaid attachment has no content to render")

        svg = self._render_placeholder(content)
        rendered_html = f'<div class="mermaid">{html.escape(content)}</div>'

        return ProcessedMedia(
            original=attachment,
            rendered_html=rendered_html,
            rendered_text=content,
            svg=svg,
            metadata={"renderer": "mermaid_placeholder", "diagram_type": self._detect_type(content)},
        )

    def _render_placeholder(self, content: str) -> str:
        """Generate an SVG placeholder with embedded mermaid source."""
        escaped = html.escape(content)
        diagram_type = self._detect_type(content)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" class="mermaid-placeholder" '
            f'data-diagram-type="{diagram_type}">'
            f"<text x=\"10\" y=\"20\" font-family=\"monospace\" font-size=\"12\">"
            f"[Mermaid: {diagram_type}]</text>"
            f'<metadata>{escaped}</metadata>'
            f"</svg>"
        )

    def _detect_type(self, content: str) -> str:
        """Detect the Mermaid diagram type from the first line."""
        first_line = content.strip().split("\n")[0].strip().lower()
        if first_line.startswith("graph"):
            return "flowchart"
        if first_line.startswith("sequencediagram"):
            return "sequence"
        if first_line.startswith("classDiagram"):
            return "class"
        if first_line.startswith("gantt"):
            return "gantt"
        if first_line.startswith("pie"):
            return "pie"
        return "unknown"


class ImageRenderer:
    """Renders image attachments to HTML img tags."""

    @property
    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    def process(self, attachment: MediaAttachment) -> ProcessedMedia:
        alt = attachment.metadata.get("alt", attachment.filename or "image")
        url = attachment.url or ""
        rendered_html = f'<img src="{html.escape(url)}" alt="{html.escape(alt)}" />'
        rendered_text = f"[Image: {alt}]"

        return ProcessedMedia(
            original=attachment,
            rendered_html=rendered_html,
            rendered_text=rendered_text,
            metadata={"renderer": "image"},
        )


class FileRenderer:
    """Renders file attachments as download cards."""

    @property
    def supported_type(self) -> MediaType:
        return MediaType.FILE

    def process(self, attachment: MediaAttachment) -> ProcessedMedia:
        filename = attachment.filename or "unknown"
        size = self._format_size(attachment.size_bytes)
        url = attachment.url or "#"

        rendered_html = (
            f'<div class="file-card">'
            f'<a href="{html.escape(url)}" download="{html.escape(filename)}">'
            f"{html.escape(filename)}</a>"
            f"<span>{size}</span>"
            f"</div>"
        )
        rendered_text = f"[File: {filename} ({size})]"

        return ProcessedMedia(
            original=attachment,
            rendered_html=rendered_html,
            rendered_text=rendered_text,
            metadata={"renderer": "file"},
        )

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes <= 0:
            return "unknown size"
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
            size_bytes /= 1024  # type: ignore[assignment]
        return f"{size_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# MediaRegistry
# ---------------------------------------------------------------------------


class MediaRegistry:
    """Dispatches media processing to the appropriate renderer.

    Pre-registers built-in renderers; additional processors can be
    registered at runtime for custom media types.
    """

    def __init__(self, *, register_defaults: bool = True) -> None:
        self._processors: dict[MediaType, MediaProcessor] = {}
        if register_defaults:
            self.register(MarkdownRenderer())
            self.register(MermaidRenderer())
            self.register(ImageRenderer())
            self.register(FileRenderer())

    def register(self, processor: MediaProcessor) -> None:
        self._processors[processor.supported_type] = processor

    def process(self, attachment: MediaAttachment) -> ProcessedMedia:
        """Process an attachment using the registered renderer."""
        processor = self._processors.get(attachment.media_type)
        if not processor:
            return ProcessedMedia(
                original=attachment,
                rendered_text=f"[Unsupported media: {attachment.media_type.value}]",
                metadata={"renderer": "fallback", "unsupported": True},
            )
        return processor.process(attachment)

    def supports(self, media_type: MediaType) -> bool:
        return media_type in self._processors

    @property
    def supported_types(self) -> list[MediaType]:
        return list(self._processors.keys())


__all__ = [
    "FileRenderer",
    "ImageRenderer",
    "MarkdownRenderer",
    "MediaAttachment",
    "MediaError",
    "MediaProcessor",
    "MediaRegistry",
    "MediaType",
    "MermaidRenderer",
    "ProcessedMedia",
]
