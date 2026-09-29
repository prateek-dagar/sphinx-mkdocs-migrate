"""Generic declarative rule engine for evaluating DocumentIR trees without procedural construct branching."""

import hashlib
from typing import List, Dict, Optional
from ..parsing.markdown_ir import BaseIRNode, NodeKind, DocumentIR
from .models import MigrationRule, RuleEvaluation, MigrationAction
from .catalog import DEFAULT_RULES


class MigrationRuleEngine:
    """Evaluates DocumentIR nodes purely by interpreting declarative MigrationRule contracts."""

    def __init__(self, custom_rules: Optional[List[MigrationRule]] = None):
        self.rules: List[MigrationRule] = (
            custom_rules if custom_rules is not None else list(DEFAULT_RULES)
        )
        self._rules_by_kind: Dict[NodeKind, List[MigrationRule]] = {}
        for rule in self.rules:
            self._rules_by_kind.setdefault(rule.source_kind, []).append(rule)

    def evaluate_node(self, node: BaseIRNode) -> Optional[RuleEvaluation]:
        """Generic evaluation: finds matching rules for node kind and delegates to rule contract."""
        matching_rules = self._rules_by_kind.get(node.kind, [])
        for rule in matching_rules:
            if rule.matches(node):
                return rule.evaluate(node)
        return None

    def evaluate_document(self, doc_ir: DocumentIR) -> List[RuleEvaluation]:
        """Evaluates all nodes across a DocumentIR tree and aggregates rule evaluations."""
        evaluations: List[RuleEvaluation] = []
        for node in doc_ir.walk():
            res = self.evaluate_node(node)
            if res is not None:
                evaluations.append(res)
        return evaluations

    def create_actions(
        self, doc_ir: DocumentIR, raw_lines: Optional[List[str]] = None
    ) -> List[MigrationAction]:
        """Generates normalized MigrationAction items with stable source-span IDs and fingerprints."""
        actions: List[MigrationAction] = []

        # Helper to compute exact source span text
        def get_span_fingerprint(start_l: int, end_l: int) -> str:
            if raw_lines and 1 <= start_l <= len(raw_lines):
                end_idx = min(end_l, len(raw_lines))
                span_text = "\n".join(raw_lines[start_l - 1 : end_idx])
                return hashlib.sha256(span_text.encode("utf-8")).hexdigest()[:16]
            return ""

        for node in doc_ir.nodes:
            # We evaluate actions on nodes
            self._collect_actions(node, doc_ir.file_path, get_span_fingerprint, actions)
        return actions

    def _collect_actions(
        self,
        node: BaseIRNode,
        file_path: str,
        fp_helper,
        actions: List[MigrationAction],
    ):
        evaluation = self.evaluate_node(node)
        if evaluation is not None:
            stable_span_key = (
                f"{file_path}:{node.start_line}-{node.end_line}:{evaluation.rule_id}"
            )
            action_id = f"act_{hashlib.sha256(stable_span_key.encode('utf-8')).hexdigest()[:12]}"

            target_directive = (
                evaluation.target.directive_name if evaluation.target else None
            )
            action = MigrationAction(
                action_id=action_id,
                rule_id=evaluation.rule_id,
                source_file=file_path,
                start_line=node.start_line,
                end_line=node.end_line,
                classification=evaluation.classification,
                source_kind=node.kind,
                source_span_fingerprint=fp_helper(node.start_line, node.end_line),
                target_directive=target_directive,
                required_extensions=evaluation.required_extensions,
                required_packages=evaluation.required_packages,
                preserves=evaluation.preserved_attributes,
                manual_instruction=evaluation.action_item,
                description=evaluation.rationale,
            )
            actions.append(action)

        # For container nodes whose children also have actions (e.g. tabs or dropdowns)
        for child in node.children:
            self._collect_actions(child, file_path, fp_helper, actions)
