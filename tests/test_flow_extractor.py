"""Tests for Phase 2: Strongly-Typed Semantic Flow Extraction, Invariants, and Golden IR Fixtures."""
import pytest
from pathlib import Path
from sphinx_mkdocs_migrate.parsing.flow_extractor import DocumentFlowExtractor
from sphinx_mkdocs_migrate.parsing.doc_ir import (
    DocumentElementType,
    HeadingElement,
    ParagraphElement,
    CodeBlockElement,
    AdmonitionElement,
    ListElement,
    ListItemElement,
    ApiDocumentationRequest,
    ApiObjectKind,
    MemberSelection,
    RawHtmlElement,
    UnknownElement,
    DOCUMENTATION_IR_SCHEMA_VERSION
)

def test_flow_extractor_preserves_exact_inter_block_order():
    """Invariant: Inter-block heterogeneous sequence (Heading -> Paragraph -> API -> Paragraph -> Code -> API -> Heading) is strictly preserved."""
    markdown_text = '''# API Reference

Introductory prose describing the package.

## Core Module

::: pythonjsonlogger.core.BaseJsonFormatter

Detailed explanation of formatter options.

```python
formatter = BaseJsonFormatter()
```

::: pythonjsonlogger.core.merge_record_extra

## Conclusion

Final concluding remarks.
'''
    extractor = DocumentFlowExtractor(file_path="docs/api.md")
    page = extractor.extract_from_text(markdown_text)

    flow = page.flow.elements
    assert len(flow) == 9

    # Invariant 1: Element sequence types match exact source order
    expected_types = [
        DocumentElementType.HEADING,
        DocumentElementType.PARAGRAPH,
        DocumentElementType.HEADING,
        DocumentElementType.API_REQUEST,
        DocumentElementType.PARAGRAPH,
        DocumentElementType.CODE_BLOCK,
        DocumentElementType.API_REQUEST,
        DocumentElementType.HEADING,
        DocumentElementType.PARAGRAPH,
    ]
    actual_types = [e.element_type for e in flow]
    assert actual_types == expected_types

    # Invariant 2: Construct IDs and Order Indices are strictly monotonic and deterministic
    for idx, elem in enumerate(flow):
        assert elem.source_order_index == idx
        assert elem.construct_id == f"doc:docs/api.md:elem:{idx:04d}"
        assert elem.source_span.file == "docs/api.md"
        assert elem.source_span.start_line >= 1

    # Invariant 3: API Documentation Requests carry symbol and inferred kind
    api_elem_1 = flow[3]
    assert isinstance(api_elem_1.content, ApiDocumentationRequest)
    assert api_elem_1.content.object_path == "pythonjsonlogger.core.BaseJsonFormatter"
    assert api_elem_1.content.object_kind == ApiObjectKind.CLASS

    api_elem_2 = flow[6]
    assert isinstance(api_elem_2.content, ApiDocumentationRequest)
    assert api_elem_2.content.object_path == "pythonjsonlogger.core.merge_record_extra"
    assert api_elem_2.content.object_kind == ApiObjectKind.FUNCTION

def test_flow_extractor_raw_html_and_admonition_preservation():
    """Invariant: Raw HTML and Admonitions are preserved without silent disappearance."""
    markdown_text = '''# Guide

!!! warning "Deprecated"
    This feature is deprecated in 4.0.

<div class="custom-card">
    <span>Custom HTML</span>
</div>
'''
    extractor = DocumentFlowExtractor(file_path="docs/guide.md")
    page = extractor.extract_from_text(markdown_text)

    flow = page.flow.elements
    assert len(flow) == 3

    assert flow[0].element_type == DocumentElementType.HEADING
    assert flow[1].element_type == DocumentElementType.ADMONITION
    assert flow[2].element_type == DocumentElementType.RAW_HTML

    adm = flow[1].content
    assert isinstance(adm, AdmonitionElement)
    assert adm.kind == "warning"
    assert adm.title == "Deprecated"

    raw = flow[2].content
    assert isinstance(raw, RawHtmlElement)
    assert "custom-card" in raw.raw_html

def test_flow_extractor_mkautodoc_and_structured_lists():
    """Invariant: mkautodoc directives, :docstring: flags, explicit member lists, and ordered/unordered lists are normalized."""
    markdown_text = '''# Developer Interface

## Helper Functions

::: httpx.request
    :docstring:

## Client

::: httpx.Client
    :docstring:
    :members: headers cookies params auth request get close

## Response

*An HTTP response.*

* `def __init__(...)`
* `.status_code` - **int**
* `.headers` - **Headers**
'''
    extractor = DocumentFlowExtractor(
        file_path="docs/api.md",
        mkdocs_config={"markdown_extensions": ["mkautodoc"]}
    )
    page = extractor.extract_from_text(markdown_text)
    elements = page.flow.elements

    assert len(elements) == 8
    assert elements[0].element_type == DocumentElementType.HEADING
    assert elements[1].element_type == DocumentElementType.HEADING
    assert elements[2].element_type == DocumentElementType.API_REQUEST
    assert elements[3].element_type == DocumentElementType.HEADING
    assert elements[4].element_type == DocumentElementType.API_REQUEST
    assert elements[5].element_type == DocumentElementType.HEADING
    assert elements[6].element_type == DocumentElementType.PARAGRAPH
    assert elements[7].element_type == DocumentElementType.LIST

    # Verify function API request with :docstring:
    func_req = elements[2].content
    assert isinstance(func_req, ApiDocumentationRequest)
    assert func_req.object_path == "httpx.request"
    assert func_req.handler == "mkautodoc"
    assert func_req.include_docstring is True
    assert func_req.member_selection == MemberSelection.NOT_SPECIFIED
    assert func_req.explicit_members == []
    assert func_req.raw_options == {"docstring": True}

    # Verify class API request with explicit members
    class_req = elements[4].content
    assert isinstance(class_req, ApiDocumentationRequest)
    assert class_req.object_path == "httpx.Client"
    assert class_req.handler == "mkautodoc"
    assert class_req.include_docstring is True
    assert class_req.member_selection == MemberSelection.EXPLICIT
    assert class_req.explicit_members == ["headers", "cookies", "params", "auth", "request", "get", "close"]

    # Verify list typing
    list_elem = elements[7].content
    assert isinstance(list_elem, ListElement)
    assert list_elem.ordered is False
    assert len(list_elem.items) == 3
    assert "def __init__" in list_elem.items[0].text
    assert ".status_code" in list_elem.items[1].text
    assert ".headers" in list_elem.items[2].text
