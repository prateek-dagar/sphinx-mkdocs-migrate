import ast
from pathlib import Path
from enum import Enum
from typing import Dict, Optional, List, Tuple, Any


class SymbolKind(str, Enum):
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    ATTRIBUTE = "ATTRIBUTE"
    UNKNOWN = "UNKNOWN"


class ResolutionStatus(str, Enum):
    STATICALLY_RESOLVED = "STATICALLY_RESOLVED"
    REEXPORT = "REEXPORT"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class SymbolResolution:
    def __init__(
        self,
        symbol_path: str,
        kind: SymbolKind,
        status: ResolutionStatus,
        source_file: Optional[str] = None,
        line_no: Optional[int] = None,
        members: Optional[List[str]] = None,
        reexport_target: Optional[str] = None,
        rationale: str = "",
    ):
        self.symbol_path = symbol_path
        self.kind = kind
        self.status = status
        self.source_file = source_file
        self.line_no = line_no
        self.members = members or []
        self.reexport_target = reexport_target
        self.rationale = rationale

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_path": self.symbol_path,
            "kind": self.kind.value,
            "status": self.status.value,
            "source_file": self.source_file,
            "line_no": self.line_no,
            "members": self.members,
            "reexport_target": self.reexport_target,
            "rationale": self.rationale,
        }


class StaticSymbolResolver:
    """Statically inspects Python source trees via AST to determine symbol kinds and members without code execution."""

    def __init__(self, src_root: Path):
        self.src_root = src_root
        self._module_trees: Dict[str, Tuple[Path, ast.Module]] = {}
        self._index_modules()

    def _index_modules(self):
        for py_path in sorted(self.src_root.rglob("*.py")):
            rel_parts = py_path.relative_to(self.src_root).with_suffix("").parts
            if rel_parts[-1] == "__init__":
                mod_name = ".".join(rel_parts[:-1])
            else:
                mod_name = ".".join(rel_parts)

            try:
                tree = ast.parse(
                    py_path.read_text(encoding="utf-8"), filename=str(py_path)
                )
                self._module_trees[mod_name] = (py_path, tree)
            except Exception:
                continue

    def resolve(self, symbol_path: str) -> SymbolResolution:
        # 1. Exact module match
        if symbol_path in self._module_trees:
            py_path, tree = self._module_trees[symbol_path]
            # Collect top-level public members
            members = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    members.append(f"class {node.name}")
                elif isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not node.name.startswith("_"):
                    members.append(f"func {node.name}")
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and not target.id.startswith("_")
                            and target.id.isupper()
                        ):
                            members.append(f"attr {target.id}")
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(
                        node.target, ast.Name
                    ) and not node.target.id.startswith("_"):
                        members.append(f"attr {node.target.id}")
            return SymbolResolution(
                symbol_path=symbol_path,
                kind=SymbolKind.MODULE,
                status=ResolutionStatus.STATICALLY_RESOLVED,
                source_file=str(py_path.relative_to(self.src_root)),
                line_no=1,
                members=members,
                rationale="Matched physical module file",
            )

        # 2. Sub-symbol lookup (class, function, method, attribute)
        parts = symbol_path.split(".")
        # Try progressively shorter module prefixes
        for i in range(len(parts) - 1, 0, -1):
            mod_candidate = ".".join(parts[:i])
            sub_symbol_parts = parts[i:]

            if mod_candidate in self._module_trees:
                py_path, tree = self._module_trees[mod_candidate]
                rel_file = str(py_path.relative_to(self.src_root))

                # Check for explicit re-export in AST: from .other import Foo or from pkg.core import Foo
                for node in tree.body:
                    if isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            if alias.asname == sub_symbol_parts[0] or (
                                alias.name == sub_symbol_parts[0] and not alias.asname
                            ):
                                target_mod = node.module or ""
                                reexport_full = (
                                    f"{target_mod}.{alias.name}"
                                    if target_mod
                                    else alias.name
                                )
                                return SymbolResolution(
                                    symbol_path=symbol_path,
                                    kind=SymbolKind.UNKNOWN,
                                    status=ResolutionStatus.REEXPORT,
                                    source_file=rel_file,
                                    line_no=node.lineno,
                                    reexport_target=reexport_full,
                                    rationale=f"Imported/Re-exported via 'from {node.module} import {alias.name}'",
                                )

                # Single-level symbol inside module (Class, Function, Attribute)
                if len(sub_symbol_parts) == 1:
                    target_name = sub_symbol_parts[0]
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef) and node.name == target_name:
                            class_methods = [
                                n.name
                                for n in node.body
                                if isinstance(
                                    n, (ast.FunctionDef, ast.AsyncFunctionDef)
                                )
                                and not n.name.startswith("_")
                            ]
                            return SymbolResolution(
                                symbol_path=symbol_path,
                                kind=SymbolKind.CLASS,
                                status=ResolutionStatus.STATICALLY_RESOLVED,
                                source_file=rel_file,
                                line_no=node.lineno,
                                members=class_methods,
                                rationale="Statically resolved class definition",
                            )
                        elif (
                            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and node.name == target_name
                        ):
                            return SymbolResolution(
                                symbol_path=symbol_path,
                                kind=SymbolKind.FUNCTION,
                                status=ResolutionStatus.STATICALLY_RESOLVED,
                                source_file=rel_file,
                                line_no=node.lineno,
                                rationale="Statically resolved function definition",
                            )
                        elif isinstance(node, ast.Assign):
                            for target in node.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == target_name
                                ):
                                    return SymbolResolution(
                                        symbol_path=symbol_path,
                                        kind=SymbolKind.ATTRIBUTE,
                                        status=ResolutionStatus.STATICALLY_RESOLVED,
                                        source_file=rel_file,
                                        line_no=node.lineno,
                                        rationale="Statically resolved module-level attribute/constant",
                                    )
                        elif isinstance(node, ast.AnnAssign):
                            if (
                                isinstance(node.target, ast.Name)
                                and node.target.id == target_name
                            ):
                                return SymbolResolution(
                                    symbol_path=symbol_path,
                                    kind=SymbolKind.ATTRIBUTE,
                                    status=ResolutionStatus.STATICALLY_RESOLVED,
                                    source_file=rel_file,
                                    line_no=node.lineno,
                                    rationale="Statically resolved annotated attribute/typealias",
                                )

                # Two-level symbol: Class.method or Class.attribute
                elif len(sub_symbol_parts) == 2:
                    cls_name, member_name = sub_symbol_parts
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef) and node.name == cls_name:
                            for member_node in node.body:
                                if (
                                    isinstance(
                                        member_node,
                                        (ast.FunctionDef, ast.AsyncFunctionDef),
                                    )
                                    and member_node.name == member_name
                                ):
                                    return SymbolResolution(
                                        symbol_path=symbol_path,
                                        kind=SymbolKind.METHOD,
                                        status=ResolutionStatus.STATICALLY_RESOLVED,
                                        source_file=rel_file,
                                        line_no=member_node.lineno,
                                        rationale=f"Statically resolved method on class {cls_name}",
                                    )
                                elif isinstance(member_node, ast.Assign):
                                    for target in member_node.targets:
                                        if (
                                            isinstance(target, ast.Name)
                                            and target.id == member_name
                                        ):
                                            return SymbolResolution(
                                                symbol_path=symbol_path,
                                                kind=SymbolKind.ATTRIBUTE,
                                                status=ResolutionStatus.STATICALLY_RESOLVED,
                                                source_file=rel_file,
                                                line_no=member_node.lineno,
                                                rationale=f"Statically resolved class attribute on {cls_name}",
                                            )

        return SymbolResolution(
            symbol_path=symbol_path,
            kind=SymbolKind.UNKNOWN,
            status=ResolutionStatus.UNRESOLVED,
            rationale="Symbol path could not be resolved in the static AST index",
        )


if __name__ == "__main__":
    src_root = Path("/Users/prateekdagar/workspace/python-json-logger/src")
    resolver = StaticSymbolResolver(src_root)

    test_symbols = [
        # Modules
        "pythonjsonlogger.core",
        "pythonjsonlogger.json",
        "pythonjsonlogger.defaults",
        "pythonjsonlogger.utils",
        # Classes
        "pythonjsonlogger.core.BaseJsonFormatter",
        "pythonjsonlogger.json.JsonFormatter",
        "pythonjsonlogger.json.JsonEncoder",
        # Functions
        "pythonjsonlogger.core.merge_record_extra",
        "pythonjsonlogger.utils.package_is_available",
        # Attributes / Constants
        "pythonjsonlogger.core.RESERVED_ATTRS",
        "pythonjsonlogger.core.LogData",
        # Methods
        "pythonjsonlogger.core.BaseJsonFormatter.format",
        "pythonjsonlogger.core.BaseJsonFormatter.add_fields",
        # Re-exports / Root package aliasing
        "pythonjsonlogger.jsonlogger.JsonFormatter",
        # Unresolved
        "pythonjsonlogger.nonexistent.Symbol",
    ]

    print("======================================================================")
    print("        PHASE 4C.3: STATIC API SYMBOL KIND & RESOLUTION AUDIT         ")
    print("======================================================================")
    print(f"Source Root: {src_root}")
    print(f"Indexed Modules: {len(resolver._module_trees)}\n")

    for sym in test_symbols:
        res = resolver.resolve(sym)
        members_str = (
            f" [members: {', '.join(res.members[:4])}...]" if res.members else ""
        )
        print(f"• {res.symbol_path}")
        print(f"    Kind:       {res.kind.value}")
        print(f"    Status:     {res.status.value}")
        if res.source_file:
            print(f"    Source:     {res.source_file}:{res.line_no}")
        if res.reexport_target:
            print(f"    Target:     {res.reexport_target}")
        print(f"    Rationale:  {res.rationale}{members_str}")
        print()
    print("======================================================================")
