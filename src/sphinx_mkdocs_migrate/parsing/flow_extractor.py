"""Deterministic Source Document Flow Extractor.

Transforms raw Markdown text into a strongly-typed DocumentFlowSpec containing an ordered,
heterogeneous sequence of DocumentElements with exact SourceSpans, stable construct_ids,
and parsed ApiDocumentationRequests (including mkdocstrings and mkautodoc options and intent).
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .doc_ir import (
    DocumentFlowSpec,
    DocumentElement,
    DocumentElementType,
    SourceSpan,
    HeadingElement,
    ParagraphElement,
    ListElement,
    ListItemElement,
    CodeBlockElement,
    AdmonitionElement,
    SnippetElement,
    ApiDocumentationRequest,
    ApiObjectKind,
    MemberSelection,
    SummaryMode,
    ResolutionStatus,
    RawHtmlElement,
    UnknownElement,
    DocumentationPage,
    DocumentationLink,
    AssetReference,
    DocumentElementContent,
)
from .markdown_ir import BaseIRNode, NodeKind
from .markdown import MarkdownParser

RE_MKAUTODOC_FLAG = re.compile(
    r"^[ ]{4,}:(?P<flag>[a-zA-Z0-9_]+):(?:[ ]+(?P<val>.*))?$"
)
RE_KEY_VAL_OPT = re.compile(r"^[ ]{4,}(?P<key>[a-zA-Z0-9_]+):[ ]*(?P<val>.*)$")


class DocumentFlowExtractor:
    """Extracts strongly-typed DocumentFlowSpec and DocumentationPage from Markdown text/files."""

    def __init__(
        self, file_path: str = "", mkdocs_config: Optional[Dict[str, Any]] = None
    ):
        self.file_path = file_path
        self.mkdocs_config = mkdocs_config or {}
        self.parser = MarkdownParser()

    def extract_from_file(
        self, file_path: Path, rel_path: Optional[str] = None
    ) -> DocumentationPage:
        display_path = rel_path if rel_path is not None else str(file_path)
        content = file_path.read_text(encoding="utf-8")
        return self.extract_from_text(content, display_path)

    def extract_from_text(self, text: str, file_path: str = "") -> DocumentationPage:
        display_path = file_path or self.file_path
        doc_ir = self.parser.parse_text(text, file_path=display_path)

        flow_elements: List[DocumentElement] = []
        outgoing_links: List[DocumentationLink] = []
        referenced_assets: List[AssetReference] = []
        page_title: Optional[str] = None

        raw_lines = text.splitlines()
        order_index = 0

        for node in doc_ir.nodes:
            elem, links, assets = self._convert_ir_node_to_flow_element(
                node, order_index, display_path, raw_lines
            )
            if elem:
                flow_elements.append(elem)
                order_index += 1
                if elem.element_type == DocumentElementType.HEADING:
                    if (
                        page_title is None
                        and isinstance(elem.content, HeadingElement)
                        and elem.content.level == 1
                    ):
                        page_title = elem.content.text
            outgoing_links.extend(links)
            referenced_assets.extend(assets)

        flow_spec = DocumentFlowSpec(source_file=display_path, elements=flow_elements)

        logical_route = display_path
        if logical_route.endswith(".md"):
            logical_route = logical_route[:-3]
        if logical_route.endswith("/index"):
            logical_route = logical_route[: -len("/index")]
        elif logical_route == "index":
            logical_route = ""

        return DocumentationPage(
            source_file=display_path,
            logical_route=logical_route,
            title=page_title,
            flow=flow_spec,
            outgoing_links=outgoing_links,
            referenced_assets=referenced_assets,
        )

    def _convert_ir_node_to_flow_element(
        self, node: BaseIRNode, order_index: int, file_path: str, raw_lines: List[str]
    ) -> Tuple[
        Optional[DocumentElement], List[DocumentationLink], List[AssetReference]
    ]:
        construct_id = f"doc:{file_path}:elem:{order_index:04d}"
        source_span = SourceSpan(
            file=file_path, start_line=node.start_line, end_line=node.end_line
        )

        links: List[DocumentationLink] = []
        assets: List[AssetReference] = []

        if node.kind == NodeKind.HEADING:
            level = node.metadata.get("level", 1)
            text = node.metadata.get("text", node.raw_text).strip()
            anchor_id = node.metadata.get("id")
            content: DocumentElementContent = HeadingElement(
                level=level, text=text, anchor_id=anchor_id
            )
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.HEADING,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.PARAGRAPH:
            text = node.raw_text.strip()
            re_link = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<target>[^\)]+)\)")
            re_img = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^\)]+)\)")

            for m in re_img.finditer(text):
                src = m.group("src")
                assets.append(
                    AssetReference(
                        source_construct_id=construct_id,
                        source_path=src,
                        asset_kind="image",
                    )
                )

            for m in re_link.finditer(text):
                target = m.group("target")
                is_internal = not (
                    target.startswith("http://")
                    or target.startswith("https://")
                    or target.startswith("//")
                )
                link_k = (
                    "internal_page"
                    if is_internal and target.endswith(".md")
                    else (
                        "internal_anchor"
                        if target.startswith("#")
                        else ("external_url" if not is_internal else "internal_page")
                    )
                )
                links.append(
                    DocumentationLink(
                        source_construct_id=construct_id,
                        target=target,
                        link_kind=link_k,
                        resolved=False,
                    )
                )

            content = ParagraphElement(text=text)
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.PARAGRAPH,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.LIST:
            is_ordered = node.metadata.get("token_tag") == "ol"
            list_items = self._convert_list_items(
                node.children, construct_id, links, assets
            )
            content = ListElement(ordered=is_ordered, items=list_items)
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.LIST,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.CODE_BLOCK:
            lang = node.metadata.get("language")
            title = node.metadata.get("title")
            content = CodeBlockElement(language=lang, code=node.raw_text, title=title)
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.CODE_BLOCK,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.ADMONITION:
            kind = node.metadata.get("admonition_type", "note")
            title = node.metadata.get("title")
            body_text = "\n".join(c.raw_text for c in node.children)
            content = AdmonitionElement(kind=kind, title=title, content_text=body_text)
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.ADMONITION,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.API_DIRECTIVE:
            symbol = node.metadata.get("symbol", "")
            node_text = node.raw_text
            raw_opts: Dict[str, Any] = {}

            # Parse options from node.raw_text (YAML for mkdocstrings or regex flags for mkautodoc)
            has_mkautodoc_flags = any(
                RE_MKAUTODOC_FLAG.match(line) for line in node_text.splitlines()[1:]
            )
            if not has_mkautodoc_flags:
                remaining_lines = "\n".join(node_text.splitlines()[1:])
                if remaining_lines.strip():
                    try:
                        import yaml

                        parsed_yaml = yaml.safe_load(remaining_lines)
                        if isinstance(parsed_yaml, dict):
                            for k, v in parsed_yaml.items():
                                raw_opts[k] = v
                            if "options" in parsed_yaml and isinstance(
                                parsed_yaml["options"], dict
                            ):
                                for k, v in parsed_yaml["options"].items():
                                    raw_opts[k] = v
                    except Exception:
                        pass

            for line in node_text.splitlines()[1:]:
                m_flag = RE_MKAUTODOC_FLAG.match(line)
                if m_flag:
                    f_name = m_flag.group("flag")
                    f_val = m_flag.group("val")
                    raw_opts[f_name] = f_val.strip() if f_val else True
                    continue
                m_opt = RE_KEY_VAL_OPT.match(line)
                if m_opt:
                    raw_opts.setdefault(m_opt.group("key"), m_opt.group("val").strip())

            # Determine handler provenance
            md_exts = self.mkdocs_config.get("markdown_extensions", [])
            has_mkautodoc = any(
                (ext == "mkautodoc" or (isinstance(ext, dict) and "mkautodoc" in ext))
                for ext in md_exts
            )
            handler = "mkautodoc" if has_mkautodoc else "mkdocstrings.python"

            # Normalize options semantically
            normalized_opts = raw_opts.copy()
            include_docstring = True
            member_selection = MemberSelection.NOT_SPECIFIED
            explicit_members: List[str] = []

            # Handle :docstring:
            if "docstring" in raw_opts:
                include_docstring = True

            # Handle :members:
            if "members" in raw_opts:
                m_val = raw_opts["members"]
                if m_val is True or m_val == "":
                    member_selection = MemberSelection.ALL_PUBLIC
                else:
                    member_selection = MemberSelection.EXPLICIT
                    explicit_members = [item for item in m_val.split() if item]

            # Infer summary mode
            summary_mode = SummaryMode.NOT_REQUESTED
            if "summary" in raw_opts:
                summary_mode = SummaryMode.EXPLICIT

            # Infer object kind based on symbol naming or leave UNKNOWN
            obj_kind = ApiObjectKind.UNKNOWN
            if symbol:
                last_part = symbol.split(".")[-1]
                if "Error" in last_part or "Exception" in last_part:
                    obj_kind = ApiObjectKind.EXCEPTION
                elif last_part[0].isupper():
                    obj_kind = ApiObjectKind.CLASS
                elif (
                    len(symbol.split(".")) >= 2
                    and last_part.islower()
                    and "_" not in last_part
                ):
                    # Module paths like pythonjsonlogger.core, pythonjsonlogger.defaults
                    obj_kind = ApiObjectKind.MODULE
                elif "_" in last_part or last_part.islower():
                    obj_kind = ApiObjectKind.FUNCTION

            api_req = ApiDocumentationRequest(
                construct_id=construct_id,
                source_span=source_span,
                object_path=symbol,
                object_kind=obj_kind,
                handler=handler,
                raw_options=raw_opts,
                normalized_options=normalized_opts,
                include_docstring=include_docstring,
                member_selection=member_selection,
                explicit_members=explicit_members,
                summary_mode=summary_mode,
                resolution_status=ResolutionStatus.UNRESOLVED,
            )
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.API_REQUEST,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=api_req,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.SNIPPET_INCLUDE:
            filepath = node.metadata.get("filepath", "")
            content = SnippetElement(snippet_path=filepath)
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.SNIPPET,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        elif node.kind == NodeKind.HTML_BLOCK:
            content = RawHtmlElement(raw_html=node.raw_text)
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.RAW_HTML,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

        else:
            content = UnknownElement(
                tag_or_type=str(node.kind),
                raw_content=node.raw_text,
                rationale=f"Unhandled NodeKind {node.kind}",
            )
            return (
                DocumentElement(
                    construct_id=construct_id,
                    element_type=DocumentElementType.UNKNOWN,
                    source_order_index=order_index,
                    source_span=source_span,
                    content=content,
                ),
                links,
                assets,
            )

    def _convert_list_items(
        self,
        nodes: List[BaseIRNode],
        parent_construct_id: str,
        links: List[DocumentationLink],
        assets: List[AssetReference],
    ) -> List[ListItemElement]:
        items: List[ListItemElement] = []
        for node in nodes:
            if node.kind == NodeKind.LIST_ITEM:
                text = node.raw_text.strip()
                child_sub_items: List[ListItemElement] = []
                for ch in node.children:
                    if ch.kind == NodeKind.PARAGRAPH:
                        p_text = ch.raw_text.strip()
                        if not text:
                            text = p_text
                    elif ch.kind == NodeKind.LIST:
                        child_sub_items.extend(
                            self._convert_list_items(
                                ch.children, parent_construct_id, links, assets
                            )
                        )
                    elif ch.kind == NodeKind.LINK_REF:
                        target = ch.metadata.get("target_path", "")
                        is_ext = ch.metadata.get("is_external", False)
                        link_k = (
                            "external_url"
                            if is_ext
                            else (
                                "internal_anchor"
                                if target.startswith("#")
                                else "internal_page"
                            )
                        )
                        links.append(
                            DocumentationLink(
                                source_construct_id=parent_construct_id,
                                target=target,
                                link_kind=link_k,
                                resolved=False,
                            )
                        )

                items.append(ListItemElement(text=text, children=child_sub_items))
            elif node.kind == NodeKind.LIST:
                items.extend(
                    self._convert_list_items(
                        node.children, parent_construct_id, links, assets
                    )
                )
        return items
