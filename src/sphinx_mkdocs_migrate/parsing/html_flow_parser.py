"""HTML Semantic DOM Flow Parser.

Extracts ordered document flow, API object hierarchy, docstrings, and summary tables
directly from rendered MkDocs HTML (e.g. mkdocs build output) to serve as the empirical
ground truth for document layout and sequence.
"""

from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup, Tag


class HtmlFlowRole(str, Enum):
    HEADING = "HEADING"
    PROSE = "PROSE"
    AUTOSUMMARY = "AUTOSUMMARY"
    API_MODULE = "API_MODULE"
    API_CLASS = "API_CLASS"
    API_FUNCTION = "API_FUNCTION"
    API_ATTRIBUTE = "API_ATTRIBUTE"
    TABLE = "TABLE"
    CODE_BLOCK = "CODE_BLOCK"
    ADMONITION = "ADMONITION"
    LIST = "LIST"
    UNKNOWN = "UNKNOWN"


def _get_classes(tag: Any) -> List[str]:
    if not isinstance(tag, Tag):
        return []
    cls = tag.get("class")
    if isinstance(cls, list):
        return [str(c) for c in cls]
    elif isinstance(cls, str):
        return cls.split()
    return []


class HtmlFlowElement(BaseModel):
    """An ordered semantic element extracted from the rendered HTML DOM."""

    order_index: int
    role: HtmlFlowRole
    text: Optional[str] = None
    level: Optional[int] = None
    qname: Optional[str] = None
    directive: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    symbols: List[str] = Field(default_factory=list)
    headers: List[str] = Field(default_factory=list)
    raw_html: Optional[str] = None


class HtmlPageFlow(BaseModel):
    """Normalized ordered flow of a single rendered documentation page."""

    source_html: str
    logical_route: str
    title: Optional[str] = None
    elements: List[HtmlFlowElement] = Field(default_factory=list)


class HtmlFlowParser:
    """Parses rendered MkDocs HTML into an ordered sequence of semantic elements."""

    def __init__(self):
        pass

    def parse_file(
        self, html_path: Path, rel_route: Optional[str] = None
    ) -> HtmlPageFlow:
        """Parse an HTML file on disk."""
        content = html_path.read_text(encoding="utf-8", errors="replace")
        route = rel_route or str(html_path)
        return self.parse_html(content, route)

    def parse_html(self, html_content: str, rel_route: str = "") -> HtmlPageFlow:
        """Parse HTML string and extract sequential document flow."""
        soup = BeautifulSoup(html_content, "html.parser")
        article = (
            soup.select_one("article.md-content__inner")
            or soup.find("article")
            or soup.select_one("main")
        )

        elements: List[HtmlFlowElement] = []
        page_title: Optional[str] = None
        order_idx = 0

        if not article:
            return HtmlPageFlow(
                source_html=rel_route, logical_route=rel_route, title=None, elements=[]
            )

        # Check if the page is a mkdocstrings API module document
        doc_module = article.select_one("div.doc-module")
        if doc_module:
            # 1. Module Heading
            heading_elem = doc_module.select_one(
                "h1.doc-heading"
            ) or doc_module.select_one("h1")
            mod_qname = ""
            if heading_elem:
                heading_text = (
                    heading_elem.get_text(" ", strip=True).replace("🔗", "").strip()
                )
                page_title = heading_text
                mod_qname = heading_text
                elements.append(
                    HtmlFlowElement(
                        order_index=order_idx,
                        role=HtmlFlowRole.HEADING,
                        level=1,
                        text=heading_text,
                        qname=mod_qname,
                    )
                )
                order_idx += 1

            # 2. Walk contents sequentially (Docstring prose, Summary tables, Children)
            contents = doc_module.select_one("div.doc-contents")
            if contents:
                for child in contents.find_all(recursive=False):
                    if not isinstance(child, Tag):
                        continue

                    classes = _get_classes(child)

                    # Prose paragraphs (module docstring)
                    if child.name == "p":
                        txt = child.get_text(" ", strip=True)
                        if txt:
                            elements.append(
                                HtmlFlowElement(
                                    order_index=order_idx,
                                    role=HtmlFlowRole.PROSE,
                                    text=txt,
                                )
                            )
                            order_idx += 1

                    # Summary overview tables
                    elif child.name == "table":
                        headers = [
                            th.get_text(strip=True) for th in child.find_all("th")
                        ]
                        rows = [
                            [td.get_text(strip=True) for td in tr.find_all("td")]
                            for tr in child.find_all("tr")
                            if tr.find_all("td")
                        ]
                        symbols = [r[0] for r in rows if r]
                        has_sigs = any("(" in s for s in symbols)

                        table_role = (
                            HtmlFlowRole.AUTOSUMMARY if symbols else HtmlFlowRole.TABLE
                        )
                        elements.append(
                            HtmlFlowElement(
                                order_index=order_idx,
                                role=table_role,
                                directive="autosummary"
                                if table_role == HtmlFlowRole.AUTOSUMMARY
                                else None,
                                options={"nosignatures": not has_sigs}
                                if table_role == HtmlFlowRole.AUTOSUMMARY
                                else {},
                                symbols=symbols,
                                headers=headers,
                            )
                        )
                        order_idx += 1

                    # Code blocks
                    elif child.name == "pre" or (
                        child.name == "div" and "highlight" in classes
                    ):
                        code_txt = child.get_text().strip()
                        elements.append(
                            HtmlFlowElement(
                                order_index=order_idx,
                                role=HtmlFlowRole.CODE_BLOCK,
                                text=code_txt,
                            )
                        )
                        order_idx += 1

                    # API Objects / Children container
                    elif child.name == "div" and "doc-children" in classes:
                        child_objs = child.find_all(
                            "div", class_="doc-object", recursive=False
                        )
                        if child_objs:
                            for obj in child_objs:
                                if not isinstance(obj, Tag):
                                    continue
                                h = obj.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                                hid_val = h.get("id") if isinstance(h, Tag) else None
                                hid = str(hid_val) if hid_val is not None else None
                                obj_classes = _get_classes(obj)

                                if "doc-class" in obj_classes:
                                    role = HtmlFlowRole.API_CLASS
                                    directive = "autoclass"
                                    options = {
                                        "members": True,
                                        "undoc-members": True,
                                        "show-inheritance": True,
                                    }
                                elif "doc-function" in obj_classes:
                                    role = HtmlFlowRole.API_FUNCTION
                                    directive = "autofunction"
                                    options = {}
                                elif "doc-attribute" in obj_classes:
                                    role = HtmlFlowRole.API_ATTRIBUTE
                                    directive = "autodata"
                                    options = {}
                                else:
                                    role = HtmlFlowRole.API_MODULE
                                    directive = "automodule"
                                    options = {
                                        "members": True,
                                        "undoc-members": True,
                                        "show-inheritance": True,
                                    }

                                elements.append(
                                    HtmlFlowElement(
                                        order_index=order_idx,
                                        role=role,
                                        qname=hid or mod_qname,
                                        directive=directive,
                                        options=options,
                                    )
                                )
                                order_idx += 1
                        else:
                            # Fallback for empty doc-children container on module pages
                            if not rel_route.endswith("index.md"):
                                elements.append(
                                    HtmlFlowElement(
                                        order_index=order_idx,
                                        role=HtmlFlowRole.API_MODULE,
                                        qname=mod_qname,
                                        directive="automodule",
                                        options={
                                            "members": True,
                                            "undoc-members": True,
                                            "show-inheritance": True,
                                        },
                                    )
                                )
                                order_idx += 1

            return HtmlPageFlow(
                source_html=rel_route,
                logical_route=rel_route,
                title=page_title,
                elements=elements,
            )

        # Standard documentation page (non-module or generic markdown)
        for child in article.find_all(recursive=False):
            if not isinstance(child, Tag):
                continue

            tag = child.name
            classes = _get_classes(child)

            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                lvl = int(tag[1])
                txt = child.get_text(" ", strip=True).replace("🔗", "").strip()
                if lvl == 1 and page_title is None:
                    page_title = txt
                elements.append(
                    HtmlFlowElement(
                        order_index=order_idx,
                        role=HtmlFlowRole.HEADING,
                        level=lvl,
                        text=txt,
                    )
                )
                order_idx += 1

            elif tag == "p":
                txt = child.get_text(" ", strip=True)
                if txt:
                    elements.append(
                        HtmlFlowElement(
                            order_index=order_idx, role=HtmlFlowRole.PROSE, text=txt
                        )
                    )
                    order_idx += 1

            elif tag == "table":
                headers = [th.get_text(strip=True) for th in child.find_all("th")]
                elements.append(
                    HtmlFlowElement(
                        order_index=order_idx, role=HtmlFlowRole.TABLE, headers=headers
                    )
                )
                order_idx += 1

            elif tag in ("ul", "ol"):
                items = [
                    li.get_text(" ", strip=True)
                    for li in child.find_all("li", recursive=False)
                ]
                elements.append(
                    HtmlFlowElement(
                        order_index=order_idx,
                        role=HtmlFlowRole.LIST,
                        symbols=items,
                        options={"ordered": tag == "ol"},
                    )
                )
                order_idx += 1

            elif tag == "div" and "highlight" in classes:
                code_txt = child.get_text().strip()
                elements.append(
                    HtmlFlowElement(
                        order_index=order_idx,
                        role=HtmlFlowRole.CODE_BLOCK,
                        text=code_txt,
                    )
                )
                order_idx += 1

            elif tag in ("div", "details") and "admonition" in classes:
                kind = [c for c in classes if c != "admonition"]
                elements.append(
                    HtmlFlowElement(
                        order_index=order_idx,
                        role=HtmlFlowRole.ADMONITION,
                        text=child.get_text(" ", strip=True),
                        options={"kind": kind[0] if kind else "note"},
                    )
                )
                order_idx += 1

        return HtmlPageFlow(
            source_html=rel_route,
            logical_route=rel_route,
            title=page_title,
            elements=elements,
        )
