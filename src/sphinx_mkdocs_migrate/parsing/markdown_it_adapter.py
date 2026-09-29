"""Markdown-it-py adapter with controlled MkDocs source extension parsing."""

import re
from typing import List, Optional, Tuple
from markdown_it import MarkdownIt
from markdown_it.token import Token
from .markdown_ir import NodeKind, BaseIRNode, DocumentIR

# Controlled MkDocs / PyMdown syntax patterns
RE_ADMONITION_HEADER = re.compile(
    r"^(?P<indent>[ ]{0,3})!{3}[ ]+(?P<type>note|warning|tip|info|important|caution|danger|bug|example|quote|abstract|check|question|fail|success)(?:[ ]+\"(?P<title>[^\"]*)\")?",
    re.IGNORECASE,
)
RE_DETAILS_HEADER = re.compile(
    r"^(?P<indent>[ ]{0,3})\?{3}(?P<state>\+|-)?(?:[ ]+(?P<type>note|warning|tip|info|details))?[ ]+\"(?P<title>[^\"]+)\"",
    re.IGNORECASE,
)
RE_TAB_HEADER = re.compile(r"^(?P<indent>[ ]{0,3})={3}[ ]+\"(?P<title>[^\"]+)\"")
RE_MKDOCSTRINGS = re.compile(r"^:::[ ]+(?P<symbol>[a-zA-Z0-9_\.]+)")
RE_SNIPPET = re.compile(r"^--8<--[ ]+\"(?P<filepath>[^\"]+)\"")
RE_CODE_FENCE_START = re.compile(r"^(?P<indent>[ ]{0,3})(?P<char>`|~){3,}")


class MarkdownIRBuilder:
    """Builds a structured DocumentIR tree combining markdown-it tokens with controlled MkDocs extensions."""

    def __init__(self, file_path: str = ""):
        self.file_path = file_path
        # Initialize markdown-it for all Standard CommonMark grammar
        self.md_parser = MarkdownIt("commonmark", {"html": True}).enable("table")

    def build_from_text(self, text: str) -> DocumentIR:
        lines = text.splitlines()
        line_map = list(range(1, len(lines) + 1))
        root_nodes = self._parse_lines(lines, line_map)
        return DocumentIR(file_path=self.file_path, nodes=root_nodes)

    def _parse_lines(self, lines: List[str], line_map: List[int]) -> List[BaseIRNode]:
        if not lines:
            return []

        nodes: List[BaseIRNode] = []
        i = 0
        n = len(lines)
        chunk: List[str] = []
        chunk_line_map: List[int] = []

        def flush_chunk():
            nonlocal chunk, chunk_line_map
            if chunk:
                text_block = "\n".join(chunk)
                sub_nodes = self._parse_standard_markdown_chunk(
                    text_block, chunk_line_map
                )
                nodes.extend(sub_nodes)
                chunk = []
                chunk_line_map = []

        current_tab_set: Optional[BaseIRNode] = None

        while i < n:
            line = lines[i]
            s_line = line.strip()

            # 1. Code Fence (Fenced blocks are buffered as standard markdown for markdown-it to parse safely)
            m_fence = RE_CODE_FENCE_START.match(line)
            if m_fence:
                fence_char = m_fence.group("char")
                match_str = m_fence.group(0).strip()
                fence_len = len(match_str)

                chunk.append(line)
                chunk_line_map.append(line_map[i])
                i += 1
                while i < n:
                    cur_line = lines[i]
                    chunk.append(cur_line)
                    chunk_line_map.append(line_map[i])
                    cur_stripped = cur_line.strip()
                    if cur_stripped.startswith(fence_char * fence_len):
                        i += 1
                        break
                    i += 1
                continue

            # 2. Content Tabs (=== "Title")
            m_tab = RE_TAB_HEADER.match(line)
            if m_tab:
                flush_chunk()
                title = m_tab.group("title")
                tab_start_l = line_map[i]
                tab_header_line = line
                i += 1

                tab_body_lines: List[str] = []
                tab_body_line_map: List[int] = []

                while i < n:
                    next_l = lines[i]
                    if not next_l.strip():
                        tab_body_lines.append("")
                        tab_body_line_map.append(line_map[i])
                        i += 1
                        continue
                    if RE_TAB_HEADER.match(next_l):
                        break
                    if next_l.startswith("    ") or next_l.startswith("\t"):
                        stripped = (
                            next_l[4:] if next_l.startswith("    ") else next_l[1:]
                        )
                        tab_body_lines.append(stripped)
                        tab_body_line_map.append(line_map[i])
                        i += 1
                    else:
                        break

                # Strip trailing empty lines to determine precise end line
                while tab_body_lines and not tab_body_lines[-1].strip():
                    tab_body_lines.pop()
                    tab_body_line_map.pop()

                child_nodes = self._parse_lines(tab_body_lines, tab_body_line_map)
                tab_end_l = tab_body_line_map[-1] if tab_body_line_map else tab_start_l

                tab_item = BaseIRNode(
                    kind=NodeKind.TAB_ITEM,
                    start_line=tab_start_l,
                    end_line=tab_end_l,
                    raw_text=tab_header_line,
                    metadata={"title": title},
                    children=child_nodes,
                )

                if current_tab_set is not None:
                    current_tab_set.children.append(tab_item)
                    current_tab_set.end_line = tab_end_l
                else:
                    current_tab_set = BaseIRNode(
                        kind=NodeKind.TAB_SET,
                        start_line=tab_start_l,
                        end_line=tab_end_l,
                        raw_text="",
                        children=[tab_item],
                    )
                    nodes.append(current_tab_set)
                continue

            # Non-tab line breaks consecutive tab sets
            current_tab_set = None

            # 3. Admonitions (!!! note "Title")
            m_adm = RE_ADMONITION_HEADER.match(line)
            if m_adm:
                flush_chunk()
                adm_type = m_adm.group("type").lower()
                title = m_adm.group("title") or adm_type.capitalize()
                adm_start_l = line_map[i]
                adm_header = line
                i += 1

                adm_body_lines: List[str] = []
                adm_body_line_map: List[int] = []

                while i < n:
                    next_l = lines[i]
                    if not next_l.strip():
                        adm_body_lines.append("")
                        adm_body_line_map.append(line_map[i])
                        i += 1
                        continue
                    if next_l.startswith("    ") or next_l.startswith("\t"):
                        stripped = (
                            next_l[4:] if next_l.startswith("    ") else next_l[1:]
                        )
                        adm_body_lines.append(stripped)
                        adm_body_line_map.append(line_map[i])
                        i += 1
                    else:
                        break

                # Strip trailing empty lines
                while adm_body_lines and not adm_body_lines[-1].strip():
                    adm_body_lines.pop()
                    adm_body_line_map.pop()

                child_nodes = self._parse_lines(adm_body_lines, adm_body_line_map)
                adm_end_l = adm_body_line_map[-1] if adm_body_line_map else adm_start_l

                adm_node = BaseIRNode(
                    kind=NodeKind.ADMONITION,
                    start_line=adm_start_l,
                    end_line=adm_end_l,
                    raw_text=adm_header,
                    metadata={"admonition_type": adm_type, "title": title},
                    children=child_nodes,
                )
                nodes.append(adm_node)
                continue

            # 4. Details Dropdowns (???+ note "Title")
            m_det = RE_DETAILS_HEADER.match(line)
            if m_det:
                flush_chunk()
                title = m_det.group("title")
                state = m_det.group("state")
                is_open = state == "+"
                det_start_l = line_map[i]
                det_header = line
                i += 1

                det_body_lines: List[str] = []
                det_body_line_map: List[int] = []

                while i < n:
                    next_l = lines[i]
                    if not next_l.strip():
                        det_body_lines.append("")
                        det_body_line_map.append(line_map[i])
                        i += 1
                        continue
                    if next_l.startswith("    ") or next_l.startswith("\t"):
                        stripped = (
                            next_l[4:] if next_l.startswith("    ") else next_l[1:]
                        )
                        det_body_lines.append(stripped)
                        det_body_line_map.append(line_map[i])
                        i += 1
                    else:
                        break

                # Strip trailing empty lines
                while det_body_lines and not det_body_lines[-1].strip():
                    det_body_lines.pop()
                    det_body_line_map.pop()

                child_nodes = self._parse_lines(det_body_lines, det_body_line_map)
                det_end_l = det_body_line_map[-1] if det_body_line_map else det_start_l

                det_node = BaseIRNode(
                    kind=NodeKind.DETAILS_DROPDOWN,
                    start_line=det_start_l,
                    end_line=det_end_l,
                    raw_text=det_header,
                    metadata={"title": title, "open_state": is_open},
                    children=child_nodes,
                )
                nodes.append(det_node)
                continue

            # 5. API Directives (::: symbol)
            m_api = RE_MKDOCSTRINGS.match(s_line)
            if m_api:
                flush_chunk()
                api_start_l = line_map[i]
                api_raw_lines = [line]
                i += 1
                while i < n:
                    next_l = lines[i]
                    if (
                        next_l.startswith("    ")
                        or next_l.startswith("\t")
                        or (len(api_raw_lines) > 1 and next_l.startswith("  "))
                    ):
                        api_raw_lines.append(next_l)
                        i += 1
                        continue
                    break
                api_end_l = line_map[i - 1]
                api_node = BaseIRNode(
                    kind=NodeKind.API_DIRECTIVE,
                    start_line=api_start_l,
                    end_line=api_end_l,
                    raw_text="\n".join(api_raw_lines),
                    metadata={"symbol": m_api.group("symbol")},
                )
                nodes.append(api_node)
                continue

            # 6. Snippet Includes (--8<-- "...")
            m_snip = RE_SNIPPET.match(s_line)
            if m_snip:
                flush_chunk()
                snip_node = BaseIRNode(
                    kind=NodeKind.SNIPPET_INCLUDE,
                    start_line=line_map[i],
                    end_line=line_map[i],
                    raw_text=line,
                    metadata={"filepath": m_snip.group("filepath")},
                )
                nodes.append(snip_node)
                i += 1
                continue

            # Standard Markdown line
            chunk.append(line)
            chunk_line_map.append(line_map[i])
            i += 1

        flush_chunk()
        return nodes

    def _parse_standard_markdown_chunk(
        self, text: str, line_map: List[int]
    ) -> List[BaseIRNode]:
        tokens = self.md_parser.parse(text)
        nodes: List[BaseIRNode] = []
        stack: List[BaseIRNode] = []
        i = 0
        n = len(tokens)

        while i < n:
            token = tokens[i]

            # 1. Code Fence (handled natively by markdown-it)
            if token.type == "fence":
                start_l, end_l = self._get_lines(token, line_map)
                info = token.info.strip()
                kind = (
                    NodeKind.MERMAID_DIAGRAM
                    if info == "mermaid"
                    else NodeKind.CODE_BLOCK
                )
                fence_node = BaseIRNode(
                    kind=kind,
                    start_line=start_l,
                    end_line=end_l,
                    raw_text=token.content,
                    metadata={"info_string": info},
                )
                if stack:
                    stack[-1].children.append(fence_node)
                else:
                    nodes.append(fence_node)
                i += 1
                continue

            # 2. Heading
            if token.type == "heading_open":
                start_l, end_l = self._get_lines(token, line_map)
                level = (
                    int(token.tag[1:])
                    if len(token.tag) > 1 and token.tag[1:].isdigit()
                    else 1
                )
                title = ""
                if i + 1 < n and tokens[i + 1].type == "inline":
                    title = tokens[i + 1].content.strip()
                head_node = BaseIRNode(
                    kind=NodeKind.HEADING,
                    start_line=start_l,
                    end_line=end_l,
                    raw_text=title,
                    metadata={"level": level, "title": title},
                )
                if stack:
                    stack[-1].children.append(head_node)
                else:
                    nodes.append(head_node)
                while i < n and tokens[i].type != "heading_close":
                    i += 1
                i += 1
                continue

            # 3. Lists & Blockquotes (Containers)
            if token.type in (
                "blockquote_open",
                "bullet_list_open",
                "ordered_list_open",
                "list_item_open",
            ):
                start_l, end_l = self._get_lines(token, line_map)
                kind = (
                    NodeKind.BLOCK_QUOTE
                    if token.type == "blockquote_open"
                    else (
                        NodeKind.LIST_ITEM
                        if token.type == "list_item_open"
                        else NodeKind.LIST
                    )
                )
                container_node = BaseIRNode(
                    kind=kind,
                    start_line=start_l,
                    end_line=end_l,
                    raw_text="",
                    metadata={"token_tag": token.tag},
                )
                if stack:
                    stack[-1].children.append(container_node)
                else:
                    nodes.append(container_node)
                stack.append(container_node)
                i += 1
                continue

            if token.type in (
                "blockquote_close",
                "bullet_list_close",
                "ordered_list_close",
                "list_item_close",
            ):
                if stack:
                    stack.pop()
                i += 1
                continue

            # 4. Paragraphs & Generic Inline Links
            if token.type == "paragraph_open":
                start_l, end_l = self._get_lines(token, line_map)
                content_token = (
                    tokens[i + 1]
                    if i + 1 < n and tokens[i + 1].type == "inline"
                    else None
                )
                content_text = content_token.content.strip() if content_token else ""

                p_node = BaseIRNode(
                    kind=NodeKind.PARAGRAPH,
                    start_line=start_l,
                    end_line=end_l,
                    raw_text=content_text,
                )
                if content_token and content_token.children:
                    self._extract_generic_links(content_token.children, p_node, start_l)

                if stack:
                    stack[-1].children.append(p_node)
                else:
                    nodes.append(p_node)

                while i < n and tokens[i].type != "paragraph_close":
                    i += 1
                i += 1
                continue

            # 5. HTML Blocks
            if token.type == "html_block":
                start_l, end_l = self._get_lines(token, line_map)
                html_node = BaseIRNode(
                    kind=NodeKind.HTML_BLOCK,
                    start_line=start_l,
                    end_line=end_l,
                    raw_text=token.content,
                )
                if stack:
                    stack[-1].children.append(html_node)
                else:
                    nodes.append(html_node)
                i += 1
                continue

            i += 1

        return nodes

    def _get_lines(self, token: Token, line_map: List[int]) -> Tuple[int, int]:
        if token.map and line_map:
            start_idx = min(token.map[0], len(line_map) - 1)
            end_idx = min(max(0, token.map[1] - 1), len(line_map) - 1)
            return line_map[start_idx], line_map[end_idx]
        return 1, 1

    def _extract_generic_links(
        self, inline_children: List[Token], parent: BaseIRNode, line_no: int
    ):
        """Extracts destination-neutral link references from markdown-it inline tokens."""
        j = 0
        m = len(inline_children)
        while j < m:
            child = inline_children[j]
            if child.type == "link_open":
                href = child.attrs.get("href", "")
                link_text = ""
                if j + 1 < m and inline_children[j + 1].type == "text":
                    link_text = inline_children[j + 1].content

                is_ext = (
                    href.startswith("http://")
                    or href.startswith("https://")
                    or href.startswith("mailto:")
                )
                parent.children.append(
                    BaseIRNode(
                        kind=NodeKind.LINK_REF,
                        start_line=line_no,
                        end_line=line_no,
                        raw_text=link_text,
                        metadata={
                            "text": link_text,
                            "href": href,
                            "is_external": is_ext,
                            "target_path": href,
                        },
                    )
                )
            j += 1
