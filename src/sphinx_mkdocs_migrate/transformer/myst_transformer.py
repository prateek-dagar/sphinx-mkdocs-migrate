"""Source-preserving patch renderer transforming only targeted construct spans with safe recursive fence nesting and disjoint span guarantees."""

import re
import hashlib
from typing import List, Dict, Tuple
from ..parsing.markdown_ir import BaseIRNode, NodeKind, DocumentIR
from ..rules.models import MigrationAction
from ..analyzer.models import Classification


class StalePlanException(Exception):
    """Raised when source span fingerprint does not match the planned action fingerprint."""

    pass


class OverlappingSpanException(Exception):
    """Raised when transformation plan contains unauthorized overlapping spans that are not parent-owned."""

    pass


class MySTDocumentTransformer:
    """Transforms targeted DocumentIR spans into valid MyST Markdown using source-preserving patching,
    fingerprint stale-plan validation, safe recursive fence allocation, and disjoint parent ownership checks."""

    def __init__(
        self, actions: List[MigrationAction], strict_fingerprint: bool = False
    ):
        self.actions = actions
        self.actions_by_span: Dict[Tuple[int, int], MigrationAction] = {
            (a.start_line, a.end_line): a for a in actions
        }
        self.strict_fingerprint = strict_fingerprint

    def transform_document(
        self, doc_ir: DocumentIR, raw_source: str
    ) -> Tuple[str, int, int, int, int, int, List[str]]:
        """Source-preserving transformation:
        - Validates source span fingerprints against planned actions.
        - Verifies disjoint span invariants on root replacement spans.
        - Leaves untouched lines completely byte-for-byte identical.
        - Replaces only the outermost [start_line, end_line] slices for TRANSFORM actions.
        - Preserves original source for PRESERVE, MANUAL, and UNSUPPORTED actions.
        Returns: (transformed_text, transforms_applied, constructs_preserved, manual_reported, unsupported_reported, stale_actions_count, stale_details)
        """
        # 1. Enforce Disjoint Spans Invariant across all TRANSFORM actions in the plan
        transform_actions = [
            a for a in self.actions if a.classification == Classification.TRANSFORM
        ]
        sorted_transforms = sorted(
            transform_actions, key=lambda a: (a.start_line, -a.end_line)
        )
        for i in range(len(sorted_transforms) - 1):
            curr_a = sorted_transforms[i]
            next_a = sorted_transforms[i + 1]
            # If next start line is before curr end line, it must be strictly contained or it's an invalid partial overlap
            if next_a.start_line <= curr_a.end_line:
                if next_a.end_line > curr_a.end_line:
                    raise OverlappingSpanException(
                        f"Partial overlapping transformation spans detected between action '{curr_a.action_id}' "
                        f"[{curr_a.start_line}, {curr_a.end_line}] and '{next_a.action_id}' [{next_a.start_line}, {next_a.end_line}]."
                    )

        lines = raw_source.splitlines(keepends=True)
        raw_lines_stripped = raw_source.splitlines()
        transforms_applied = 0
        constructs_preserved = 0
        manual_reported = 0
        unsupported_reported = 0
        stale_actions_count = 0
        stale_details: List[str] = []

        # Collect non-overlapping root-level target spans to replace
        spans_to_replace: List[Tuple[int, int, str]] = []

        for node in doc_ir.nodes:
            span_key = (node.start_line, node.end_line)
            action = self.actions_by_span.get(span_key)

            if action is None:
                continue

            # Action-level Stale-Plan Fingerprint Validation
            if action.source_span_fingerprint and raw_lines_stripped:
                start_l, end_l = node.start_line, node.end_line
                if 1 <= start_l <= len(raw_lines_stripped):
                    end_idx = min(end_l, len(raw_lines_stripped))
                    current_span_text = "\n".join(
                        raw_lines_stripped[start_l - 1 : end_idx]
                    )
                    current_fp = hashlib.sha256(
                        current_span_text.encode("utf-8")
                    ).hexdigest()[:16]
                    if current_fp != action.source_span_fingerprint:
                        stale_msg = (
                            f"{action.source_file}:{start_l}-{end_l} STALE_PLAN: "
                            f"Expected fingerprint {action.source_span_fingerprint}, got {current_fp}"
                        )
                        stale_actions_count += 1
                        stale_details.append(stale_msg)
                        if self.strict_fingerprint:
                            raise StalePlanException(stale_msg)
                        # Skip stale transformation
                        continue

            if action.classification == Classification.TRANSFORM:
                rendered_myst = self._render_node_safely(node)
                spans_to_replace.append((node.start_line, node.end_line, rendered_myst))
                transforms_applied += 1
            elif action.classification == Classification.PRESERVE:
                constructs_preserved += 1
            elif action.classification == Classification.MANUAL:
                manual_reported += 1
            elif action.classification == Classification.UNSUPPORTED:
                unsupported_reported += 1

        def _sanitize_fm(text: str) -> str:
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    sanitized_header = re.sub(
                        r"(\bdate\s*:\s*)(\d{4}-\d{2}-\d{2})\b", r'\1"\2"', parts[1]
                    )
                    return "---" + sanitized_header + "---" + parts[2]
            return text

        if not spans_to_replace:
            return (
                _sanitize_fm(raw_source),
                transforms_applied,
                constructs_preserved,
                manual_reported,
                unsupported_reported,
                stale_actions_count,
                stale_details,
            )

        # Double check disjoint spans on root replacement targets
        spans_to_replace.sort(key=lambda s: s[0])
        for i in range(len(spans_to_replace) - 1):
            curr_s, curr_e, _ = spans_to_replace[i]
            next_s, next_e, _ = spans_to_replace[i + 1]
            if curr_e >= next_s:
                raise OverlappingSpanException(
                    f"Overlapping transformation spans detected: [{curr_s}, {curr_e}] and [{next_s}, {next_e}]. "
                    f"Parent containers must exclusively own child transformations."
                )

        output_lines: List[str] = []
        current_line_idx = 1

        for start_l, end_l, replacement in spans_to_replace:
            while current_line_idx < start_l:
                output_lines.append(lines[current_line_idx - 1])
                current_line_idx += 1

            if not replacement.endswith("\n"):
                replacement += "\n"
            output_lines.append(replacement)
            current_line_idx = end_l + 1

        while current_line_idx <= len(lines):
            output_lines.append(lines[current_line_idx - 1])
            current_line_idx += 1

        return (
            "".join(output_lines),
            transforms_applied,
            constructs_preserved,
            manual_reported,
            unsupported_reported,
            stale_actions_count,
            stale_details,
        )

    def _get_max_child_fence(self, node: BaseIRNode) -> int:
        """Recursively inspects node subtree to find the maximum existing or needed fence delimiter length."""
        max_len = 0
        for child in node.children:
            if child.kind == NodeKind.CODE_BLOCK:
                max_len = max(max_len, 3)
            elif child.kind in (NodeKind.ADMONITION, NodeKind.DETAILS_DROPDOWN):
                child_inner = self._get_max_child_fence(child)
                child_container_len = max(child_inner + 1, 3)
                max_len = max(max_len, child_container_len)
            elif child.kind == NodeKind.TAB_SET:
                child_inner = self._get_max_child_fence(child)
                max_len = max(max_len, child_inner + 2)  # tab-item + tab-set
            else:
                max_len = max(max_len, self._get_max_child_fence(child))
        return max_len

    def _render_node_safely(self, node: BaseIRNode, min_fence_len: int = 3) -> str:
        """Renders an IR node with strictly valid nested fence lengths:
        Outer fence = max(max_descendant_fence + 1, min_fence_len)
        """
        child_max = self._get_max_child_fence(node)
        fence_len = max(child_max + 1, min_fence_len)
        fence_marker = "`" * fence_len

        # 1. Admonitions (!!! note "Title")
        if node.kind == NodeKind.ADMONITION:
            adm_type = node.metadata.get("admonition_type", "note")
            title = node.metadata.get("title", "")

            action = self.actions_by_span.get((node.start_line, node.end_line))
            directive = (
                action.target_directive
                if action and action.target_directive
                else adm_type
            )

            if directive in (
                "note",
                "warning",
                "tip",
                "important",
                "caution",
                "danger",
                "seealso",
            ):
                header = (
                    f"{fence_marker}{{{directive}}} {title}".strip()
                    if title != directive.capitalize()
                    else f"{fence_marker}{{{directive}}}"
                )
            else:
                header = (
                    f"{fence_marker}{{admonition}} {title}\n:class: {adm_type}".strip()
                )

            body_parts = [
                self._render_child_body(child, parent_fence_len=fence_len)
                for child in node.children
            ]
            body_text = "\n\n".join(b for b in body_parts if b)
            return f"{header}\n{body_text}\n{fence_marker}"

        # 2. Content Tabs (=== "Title")
        elif node.kind == NodeKind.TAB_SET:
            tab_items_rendered: List[str] = []

            # Find the maximum fence needed by ANY tab item's content
            max_inner_fence = 0
            for tab_item in node.children:
                max_inner_fence = max(
                    max_inner_fence, self._get_max_child_fence(tab_item)
                )

            # Tab items need (max_inner_fence + 1) or at least 3
            item_fence_len = max(max_inner_fence + 1, 3)
            # Outer tab-set must strictly enclose tab-items: (item_fence_len + 1)
            outer_fence_len = max(item_fence_len + 1, min_fence_len)

            outer_fence = "`" * outer_fence_len
            item_fence = "`" * item_fence_len

            for tab_item in node.children:
                tab_title = tab_item.metadata.get("title", "Tab").strip()
                # Strip all inline backticks from tab title for clean sphinx-design label compatibility
                tab_title = tab_title.replace("`", "")
                inner_parts = [
                    self._render_child_body(c, parent_fence_len=item_fence_len)
                    for c in tab_item.children
                ]
                inner_body = "\n\n".join(b for b in inner_parts if b)
                item_rendered = (
                    f"{item_fence}{{tab-item}} {tab_title}\n{inner_body}\n{item_fence}"
                )
                tab_items_rendered.append(item_rendered)

            all_tabs_text = "\n\n".join(tab_items_rendered)
            return f"{outer_fence}{{tab-set}}\n{all_tabs_text}\n{outer_fence}"

        # 3. Details Dropdowns (???+ note "Title")
        elif node.kind == NodeKind.DETAILS_DROPDOWN:
            title = node.metadata.get("title", "Details")
            is_open = node.metadata.get("open_state", False)
            open_opt = "\n:open:" if is_open else ""

            body_parts = [
                self._render_child_body(child, parent_fence_len=fence_len)
                for child in node.children
            ]
            body_text = "\n\n".join(b for b in body_parts if b)
            return f"{fence_marker}{{dropdown}} {title}{open_opt}\n{body_text}\n{fence_marker}"

        # 4. Snippet Includes (--8<-- "path")
        elif node.kind == NodeKind.SNIPPET_INCLUDE:
            filepath = node.metadata.get("filepath", "")
            directive = (
                "include"
                if (filepath.endswith(".md") or filepath.endswith(".txt"))
                else "literalinclude"
            )
            return f"```{{{directive}}} {filepath}\n```"

        # 5. Mermaid Diagrams (```mermaid)
        elif node.kind == NodeKind.MERMAID_DIAGRAM:
            diagram_code = node.raw_text.strip()
            if diagram_code.startswith("---"):
                parts = diagram_code.split("---", 2)
                if len(parts) >= 3:
                    diagram_code = parts[2].strip()
            return f"```{{mermaid}}\n{diagram_code}\n```"

        # 6. API Directives (::: symbol)
        elif node.kind == NodeKind.API_DIRECTIVE:
            symbol = node.metadata.get("symbol", "")
            raw_text = node.raw_text

            explicit_members = []
            is_all_members = False
            for line in raw_text.splitlines():
                s = line.strip()
                if s.startswith(":members:"):
                    m_val = s[len(":members:") :].strip()
                    if m_val:
                        explicit_members = [item for item in m_val.split() if item]
                    else:
                        is_all_members = True

            last_part = symbol.split(".")[-1] if symbol else ""
            if "Error" in last_part or "Exception" in last_part:
                directive = "autoexception"
            elif last_part and last_part[0].isupper():
                directive = "autoclass"
            elif "_" in last_part or (last_part and last_part.islower()):
                directive = "autofunction"
            else:
                directive = "autoclass"

            lines = [f".. {directive}:: {symbol}"]
            if explicit_members:
                lines.append(f"    :members: {', '.join(explicit_members)}")
            elif is_all_members:
                lines.append("    :members:")

            if directive in ("autoclass", "autoexception"):
                lines.append("    :show-inheritance:")

            rst_block = "\n".join(lines)
            return f"```{{eval-rst}}\n{rst_block}\n```"

        return node.raw_text

    def _render_child_body(self, node: BaseIRNode, parent_fence_len: int) -> str:
        """Renders a child node inside a parent container directive with strictly safe fence lengths."""
        if node.kind in (
            NodeKind.ADMONITION,
            NodeKind.TAB_SET,
            NodeKind.DETAILS_DROPDOWN,
        ):
            return self._render_node_safely(
                node, min_fence_len=parent_fence_len - 1 if parent_fence_len > 3 else 3
            )
        elif node.kind == NodeKind.CODE_BLOCK:
            info = node.metadata.get("info_string", "")
            code_text = node.raw_text
            if not code_text.endswith("\n"):
                code_text += "\n"
            # Code block inside a parent container of length N must use < N backticks (typically 3)
            code_fence_len = min(3, parent_fence_len - 1) if parent_fence_len > 3 else 3
            code_fence = "`" * code_fence_len
            return f"{code_fence}{info}\n{code_text}{code_fence}"
        elif node.kind == NodeKind.PARAGRAPH:
            return node.raw_text
        elif node.kind == NodeKind.HEADING:
            level = node.metadata.get("level", 1)
            title = node.metadata.get("title", node.raw_text)
            return f"{'#' * level} {title}"
        elif node.kind == NodeKind.LIST:
            items_text = [
                self._render_child_body(item, parent_fence_len)
                for item in node.children
            ]
            return "\n".join(items_text)
        elif node.kind == NodeKind.LIST_ITEM:
            child_text = (
                "\n".join(
                    self._render_child_body(c, parent_fence_len) for c in node.children
                )
                if node.children
                else node.raw_text
            )
            lines = child_text.splitlines()
            if not lines:
                return "- "
            first_line = f"- {lines[0]}"
            rest_lines = [f"  {line_item}" for line_item in lines[1:]]
            return "\n".join([first_line] + rest_lines)
        return node.raw_text
