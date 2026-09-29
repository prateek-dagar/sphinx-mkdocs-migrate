"""Markdown parser entrypoint wrapping the markdown-it token adapter."""

from pathlib import Path
from typing import Optional
from .markdown_ir import DocumentIR
from .markdown_it_adapter import MarkdownIRBuilder


class MarkdownParser:
    """Parses markdown documents into destination-neutral DocumentIR trees via markdown-it-py."""

    def parse_file(self, file_path: Path, rel_path: Optional[str] = None) -> DocumentIR:
        display_path = rel_path if rel_path is not None else str(file_path)
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return DocumentIR(file_path=display_path, nodes=[])
        return self.parse_text(content, display_path)

    def parse_text(self, text: str, file_path: str = "") -> DocumentIR:
        builder = MarkdownIRBuilder(file_path=file_path)
        return builder.build_from_text(text)
