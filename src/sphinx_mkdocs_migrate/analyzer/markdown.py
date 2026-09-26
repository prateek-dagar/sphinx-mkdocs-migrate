"""Markdown AST analyzer inspecting DocumentIR nodes to extract migration findings."""
from pathlib import Path
from typing import List, Tuple, Optional
from ..parsing.markdown import MarkdownParser
from ..parsing.markdown_ir import NodeKind, BaseIRNode
from .models import ConstructFinding, Classification

class MarkdownAnalyzer:
    """Analyzes Markdown files by parsing them into DocumentIR and recording migration findings."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root
        self.parser = MarkdownParser()

    def analyze_file(self, file_path: Path) -> List[ConstructFinding]:
        if not file_path.exists():
            return []

        doc_ir = self.parser.parse_file(file_path)
        findings: List[ConstructFinding] = []

        def visit_node(node: BaseIRNode):
            snippet = node.raw_text.splitlines()[0] if node.raw_text.splitlines() else f"<{node.kind.value}>"

            if node.kind == NodeKind.ADMONITION:
                findings.append(ConstructFinding(
                    category="Markdown",
                    construct_type="admonition",
                    file_path=doc_ir.file_path,
                    line_number=node.start_line,
                    end_line_number=node.end_line,
                    raw_snippet=snippet,
                    classification=Classification.TRANSFORM,
                    metadata={"admonition_type": node.metadata.get("admonition_type"), "title": node.metadata.get("title")}
                ))
            elif node.kind == NodeKind.DETAILS_DROPDOWN:
                findings.append(ConstructFinding(
                    category="Markdown",
                    construct_type="details_dropdown",
                    file_path=doc_ir.file_path,
                    line_number=node.start_line,
                    end_line_number=node.end_line,
                    raw_snippet=snippet,
                    classification=Classification.TRANSFORM,
                    metadata={"title": node.metadata.get("title")}
                ))
            elif node.kind == NodeKind.TAB_SET:
                findings.append(ConstructFinding(
                    category="Markdown",
                    construct_type="tab_set",
                    file_path=doc_ir.file_path,
                    line_number=node.start_line,
                    end_line_number=node.end_line,
                    raw_snippet=snippet,
                    classification=Classification.TRANSFORM,
                    metadata={"tab_count": len(node.children)}
                ))
            elif node.kind == NodeKind.API_DIRECTIVE:
                findings.append(ConstructFinding(
                    category="API Documentation",
                    construct_type="mkdocstrings",
                    file_path=doc_ir.file_path,
                    line_number=node.start_line,
                    end_line_number=node.end_line,
                    raw_snippet=snippet,
                    classification=Classification.MANUAL,
                    metadata={"symbol": node.metadata.get("symbol")}
                ))
            elif node.kind == NodeKind.SNIPPET_INCLUDE:
                findings.append(ConstructFinding(
                    category="Markdown",
                    construct_type="snippet_include",
                    file_path=doc_ir.file_path,
                    line_number=node.start_line,
                    end_line_number=node.end_line,
                    raw_snippet=snippet,
                    classification=Classification.TRANSFORM,
                    metadata={"filepath": node.metadata.get("filepath")}
                ))
            elif node.kind == NodeKind.MERMAID_DIAGRAM:
                findings.append(ConstructFinding(
                    category="Markdown",
                    construct_type="mermaid_diagram",
                    file_path=doc_ir.file_path,
                    line_number=node.start_line,
                    end_line_number=node.end_line,
                    raw_snippet=snippet,
                    classification=Classification.TRANSFORM,
                    metadata={}
                ))
            elif node.kind == NodeKind.LINK_REF:
                href = node.metadata.get("href", "")
                if href.endswith(".md") or ".md#" in href:
                    findings.append(ConstructFinding(
                        category="Markdown",
                        construct_type="document_link",
                        file_path=doc_ir.file_path,
                        line_number=node.start_line,
                        end_line_number=node.end_line,
                        raw_snippet=href,
                        classification=Classification.PRESERVE,
                        metadata={"href": href, "text": node.metadata.get("text")}
                    ))

            # Recurse children
            for child in node.children:
                visit_node(child)

        for root_node in doc_ir.nodes:
            visit_node(root_node)

        return findings

    def analyze_directory(self, docs_dir: Path) -> Tuple[int, List[ConstructFinding]]:
        if not docs_dir.exists():
            return 0, []

        all_findings: List[ConstructFinding] = []
        md_files = list(docs_dir.rglob("*.md"))

        for md_file in md_files:
            file_findings = self.analyze_file(md_file)
            all_findings.extend(file_findings)

        return len(md_files), all_findings
