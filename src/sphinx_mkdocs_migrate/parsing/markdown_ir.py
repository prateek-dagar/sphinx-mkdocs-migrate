"""Structured Document & Block Intermediate Representation (IR)."""
from enum import Enum
from typing import List, Dict, Any, Optional, Iterator
from pydantic import BaseModel, Field

class NodeKind(str, Enum):
    DOCUMENT = "DOCUMENT"
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    BLOCK_QUOTE = "BLOCK_QUOTE"
    LIST = "LIST"
    LIST_ITEM = "LIST_ITEM"
    CODE_BLOCK = "CODE_BLOCK"
    HTML_BLOCK = "HTML_BLOCK"
    ADMONITION = "ADMONITION"
    DETAILS_DROPDOWN = "DETAILS_DROPDOWN"
    TAB_SET = "TAB_SET"
    TAB_ITEM = "TAB_ITEM"
    API_DIRECTIVE = "API_DIRECTIVE"
    MERMAID_DIAGRAM = "MERMAID_DIAGRAM"
    SNIPPET_INCLUDE = "SNIPPET_INCLUDE"
    LINK_REF = "LINK_REF"

class BaseIRNode(BaseModel):
    kind: NodeKind
    start_line: int
    end_line: int
    raw_text: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    children: List['BaseIRNode'] = Field(default_factory=list)

    def walk(self) -> Iterator['BaseIRNode']:
        """Recursively walk this node and all of its descendants."""
        yield self
        for child in self.children:
            yield from child.walk()

class DocumentIR(BaseModel):
    file_path: str
    nodes: List[BaseIRNode] = Field(default_factory=list)

    def walk(self) -> Iterator[BaseIRNode]:
        """Recursively walk all nodes in the document."""
        for node in self.nodes:
            yield from node.walk()
