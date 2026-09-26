import ast
import re
from pathlib import Path
from enum import Enum
from typing import List, Dict, Any, Optional

class DocstringLinkClassification(str, Enum):
    MKDOCS_AUTOREF = "MKDOCS_AUTOREF"             # [Text][symbol.path] or [symbol.path]
    EXTERNAL_MARKDOWN_LINK = "EXTERNAL_MD_LINK"   # [Text](http...)
    SPHINX_ROLE_CANDIDATE = "SPHINX_ROLE"         # already :class:`...` or similar
    VARIADIC_PARAMETER = "VARIADIC_PARAM"         # *args, **kwargs mentioned in params

class DocstringIssue:
    def __init__(self, file_path: str, symbol: str, line_no: int, raw_text: str, classification: DocstringLinkClassification, suggested_sphinx: Optional[str] = None):
        self.file_path = file_path
        self.symbol = symbol
        self.line_no = line_no
        self.raw_text = raw_text
        self.classification = classification
        self.suggested_sphinx = suggested_sphinx

def analyze_python_docstrings(src_dir: Path) -> List[DocstringIssue]:
    issues: List[DocstringIssue] = []
    
    for py_path in sorted(src_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        except Exception:
            continue
            
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if not doc:
                    continue
                
                symbol_name = getattr(node, "name", py_path.stem)
                doc_start_line = getattr(node, "lineno", 1)
                lines = doc.splitlines()
                
                for idx, line in enumerate(lines):
                    current_line_no = doc_start_line + idx
                    
                    # 1. Detect MkDocs autorefs: [Text][dotted.path]
                    for m in re.finditer(r"\[([^\]]+)\]\[([a-zA-Z0-9_\.]+)\]", line):
                        text, target = m.group(1), m.group(2)
                        suggested = f":class:`{text} <~{target}>`" if text != target else f":class:`~{target}`"
                        issues.append(DocstringIssue(str(py_path.name), symbol_name, current_line_no, m.group(0), DocstringLinkClassification.MKDOCS_AUTOREF, suggested))
                    
                    # 2. Detect [dotted.path][] shorthand
                    for m in re.finditer(r"\[([a-zA-Z0-9_\.]{3,})\]\[\]", line):
                        target = m.group(1)
                        issues.append(DocstringIssue(str(py_path.name), symbol_name, current_line_no, m.group(0), DocstringLinkClassification.MKDOCS_AUTOREF, f":any:`~{target}`"))

                    # 3. Detect Markdown external links: [Text](http...)
                    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^\)]+)\)", line):
                        text, url = m.group(1), m.group(2)
                        suggested = f"`{text} <{url}>`_"
                        issues.append(DocstringIssue(str(py_path.name), symbol_name, current_line_no, m.group(0), DocstringLinkClassification.EXTERNAL_MARKDOWN_LINK, suggested))

                    # 4. Detect Variadic parameter notation in docstring parameter sections
                    if re.search(r"^\s*(\*args|\*\*kwargs)\b", line) or re.search(r":param\s+(\*args|\*\*kwargs):", line):
                        issues.append(DocstringIssue(str(py_path.name), symbol_name, current_line_no, line.strip(), DocstringLinkClassification.VARIADIC_PARAMETER, "Document at class/constructor overview level rather than pseudo :param: field"))

    return issues

if __name__ == "__main__":
    src_dir = Path("/Users/prateekdagar/workspace/python-json-logger/src")
    issues = analyze_python_docstrings(src_dir)

    print("======================================================================")
    print("        PHASE 4C.2: STATIC DOCSTRING COMPATIBILITY ANALYSIS           ")
    print("======================================================================")
    print(f"Total Python Source Files Examined: {len(list(src_dir.rglob('*.py')))}")
    print(f"Total Docstring Compatibility Findings: {len(issues)}")

    classified: Dict[DocstringLinkClassification, List[DocstringIssue]] = {}
    for issue in issues:
        classified.setdefault(issue.classification, []).append(issue)

    for classification, items in classified.items():
        print(f"\n• {classification.value} ({len(items)} findings):")
        for item in items:
            print(f"   - {item.file_path}:{item.line_no} [{item.symbol}]")
            print(f"     Source Construct:   {item.raw_text}")
            print(f"     Suggested Sphinx:   {item.suggested_sphinx}")

    print("======================================================================")
