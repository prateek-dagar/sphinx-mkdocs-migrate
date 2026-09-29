"""CommonMark structural validation and isolated Sphinx build verification engine."""

import re
import sys
import shutil
import subprocess
import tempfile
import importlib.util
from pathlib import Path
from typing import List, Tuple
from markdown_it import MarkdownIt
from .models import ValidationReport, ValidationIssue, ValidationSeverity
from ..transformer.models import ProjectTransformationReport


class TransformationValidator:
    """Validates transformed Markdown via CommonMark parsing, directive structure checks, and isolated Sphinx execution."""

    def __init__(self):
        self.md_parser = MarkdownIt("commonmark", {"html": True}).enable("table")

    def validate_transformation_report(
        self,
        report: ProjectTransformationReport,
        run_sphinx_build: bool = False,
        strict_warnings: bool = False,
    ) -> ValidationReport:
        """Validates all transformed documents in a ProjectTransformationReport and optionally executes an isolated Sphinx build."""
        issues: List[ValidationIssue] = []
        cm_parse_ok = True
        struct_ok = True

        for doc in report.transformed_documents:
            doc_issues = self.validate_structural_syntax(
                doc.target_file, doc.transformed_content
            )
            issues.extend(doc_issues)
            if any(i.severity == ValidationSeverity.ERROR for i in doc_issues):
                cm_parse_ok = False
                struct_ok = False

        # Validate conf.py existence and structure
        conf_keys = [
            k for k in report.generated_sphinx_files.keys() if k.endswith("conf.py")
        ]
        if not conf_keys:
            issues.append(
                ValidationIssue(
                    file_path="conf.py",
                    severity=ValidationSeverity.ERROR,
                    issue_type="MISSING_CONF_PY",
                    message="Sphinx conf.py was not generated in transformation report.",
                )
            )
            struct_ok = False
        else:
            conf_content = report.generated_sphinx_files[conf_keys[0]]
            if "extensions =" not in conf_content or "myst_parser" not in conf_content:
                issues.append(
                    ValidationIssue(
                        file_path=conf_keys[0],
                        severity=ValidationSeverity.ERROR,
                        issue_type="INVALID_CONF_PY",
                        message="Generated conf.py is missing myst_parser extension.",
                    )
                )
                struct_ok = False

        sphinx_build_attempted = False
        sphinx_build_successful = None
        build_output = None
        sphinx_warning_count = 0
        sphinx_warnings: List[str] = []
        sphinx_theme_status = None

        # Execute real Sphinx build in an isolated sandbox directory if requested
        if run_sphinx_build and struct_ok:
            sphinx_build_attempted = True
            build_ok, output, warnings, theme_status = self._execute_real_sphinx_build(
                report, strict_warnings=strict_warnings
            )
            sphinx_build_successful = build_ok
            build_output = output
            sphinx_warnings = warnings
            sphinx_warning_count = len(warnings)
            sphinx_theme_status = theme_status

            if not build_ok:
                issue_type = (
                    "SPHINX_STRICT_WARNING_ERROR"
                    if strict_warnings and sphinx_warning_count > 0
                    else "SPHINX_BUILD_ERROR"
                )
                issues.append(
                    ValidationIssue(
                        file_path="sphinx-build",
                        severity=ValidationSeverity.ERROR,
                        issue_type=issue_type,
                        message=f"Sphinx HTML build failed{' (strict warnings mode enabled)' if strict_warnings else ''}.",
                        context_snippet=output[:600] if output else None,
                    )
                )

        err_cnt = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        warn_cnt = sum(
            1 for i in issues if i.severity == ValidationSeverity.WARNING
        ) + (sphinx_warning_count if not strict_warnings else 0)

        return ValidationReport(
            passed=(err_cnt == 0),
            total_issues=len(issues),
            errors_count=err_cnt,
            warnings_count=warn_cnt,
            issues=issues,
            commonmark_parse_successful=cm_parse_ok,
            structural_validation_successful=struct_ok,
            sphinx_build_attempted=sphinx_build_attempted,
            sphinx_build_successful=sphinx_build_successful,
            sphinx_warning_count=sphinx_warning_count,
            sphinx_warnings=sphinx_warnings,
            sphinx_theme_status=sphinx_theme_status,
            build_output=build_output,
        )

    def validate_structural_syntax(
        self, file_path: str, content: str
    ) -> List[ValidationIssue]:
        """Parses generated Markdown to ensure CommonMark validity, balanced fences, and clean construct conversion."""
        issues: List[ValidationIssue] = []

        # 1. Parse via CommonMark engine
        try:
            self.md_parser.parse(content)
        except Exception as e:
            issues.append(
                ValidationIssue(
                    file_path=file_path,
                    severity=ValidationSeverity.ERROR,
                    issue_type="PARSER_EXCEPTION",
                    message=f"CommonMark structural parsing failed: {str(e)}",
                )
            )
            return issues

        # 2. Check for balanced directive and code fences
        lines = content.splitlines()
        fence_stack: List[Tuple[int, str, int]] = []
        re_fence = re.compile(r"^(?P<indent>[ ]{0,3})(?P<char>`|~){3,}")

        for idx, line in enumerate(lines, start=1):
            m = re_fence.match(line)
            if m:
                marker_char = m.group("char")
                marker_str = m.group(0).strip()
                length = len(marker_str)

                if (
                    fence_stack
                    and fence_stack[-1][1] == marker_char
                    and length >= fence_stack[-1][2]
                ):
                    fence_stack.pop()
                else:
                    fence_stack.append((idx, marker_char, length))

        if fence_stack:
            for unclosed_l, char, length in fence_stack:
                issues.append(
                    ValidationIssue(
                        file_path=file_path,
                        line_number=unclosed_l,
                        severity=ValidationSeverity.ERROR,
                        issue_type="UNCLOSED_FENCE",
                        message=f"Unclosed code or directive fence of length {length} starting at line {unclosed_l}.",
                        context_snippet=lines[unclosed_l - 1]
                        if unclosed_l <= len(lines)
                        else None,
                    )
                )

        # 3. Check for remaining unmigrated MkDocs construct remnants outside code fences
        re_unmigrated_adm = re.compile(
            r"^[ ]{0,3}!{3}[ ]+(note|warning|tip|info|danger|caution)"
        )
        re_unmigrated_tab = re.compile(r"^[ ]{0,3}={3}[ ]+\"[^\"]+\"")

        in_code = False
        for idx, line in enumerate(lines, start=1):
            if re_fence.match(line):
                in_code = not in_code
            elif not in_code:
                if re_unmigrated_adm.match(line):
                    issues.append(
                        ValidationIssue(
                            file_path=file_path,
                            line_number=idx,
                            severity=ValidationSeverity.WARNING,
                            issue_type="UNMIGRATED_ADMONITION",
                            message=f"Unmigrated MkDocs admonition syntax detected at line {idx}.",
                            context_snippet=line,
                        )
                    )
                elif re_unmigrated_tab.match(line):
                    issues.append(
                        ValidationIssue(
                            file_path=file_path,
                            line_number=idx,
                            severity=ValidationSeverity.WARNING,
                            issue_type="UNMIGRATED_TAB",
                            message=f"Unmigrated MkDocs tab syntax detected at line {idx}.",
                            context_snippet=line,
                        )
                    )

        return issues

    def _execute_real_sphinx_build(
        self, report: ProjectTransformationReport, strict_warnings: bool = False
    ) -> Tuple[bool, str, List[str], str]:
        """Runs `sphinx-build` in an isolated sandbox copying docs, assets, and exact conf.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            docs_src = tmppath / "source"
            docs_out = tmppath / "build"
            docs_src.mkdir(parents=True)

            # Determine the exact common docs_dir prefix from the generated conf.py path
            conf_prefix_parts: Tuple[str, ...] = ()
            if report.generated_sphinx_files:
                conf_key = list(report.generated_sphinx_files.keys())[0]
                conf_key_path = Path(conf_key)
                if len(conf_key_path.parts) > 1:
                    conf_prefix_parts = conf_key_path.parts[:-1]

            # Copy docs static assets, images, examples from docs directory
            proj_root = Path(report.project_root)
            docs_dir_name = conf_prefix_parts[0] if conf_prefix_parts else "docs"
            docs_folder = (
                proj_root / docs_dir_name
                if (proj_root / docs_dir_name).is_dir()
                else (
                    proj_root / "docs" if (proj_root / "docs").is_dir() else proj_root
                )
            )
            if docs_folder.exists() and docs_folder.is_dir():
                for item in docs_folder.rglob("*"):
                    if (
                        item.is_file()
                        and not item.name.endswith(".md")
                        and not item.name.endswith(".pyc")
                    ):
                        try:
                            rel = item.relative_to(docs_folder)
                            if any(
                                part
                                in (
                                    ".git",
                                    ".venv",
                                    "venv",
                                    "__pycache__",
                                    ".pytest_cache",
                                    "site",
                                )
                                for part in rel.parts
                            ):
                                continue
                            dest_asset = docs_src / rel
                            dest_asset.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest_asset)
                        except Exception:
                            pass

            # Write transformed markdown documents directly into docs_src relative to the docs_dir
            for doc in report.transformed_documents:
                doc_path = Path(doc.target_file)
                if (
                    conf_prefix_parts
                    and doc_path.parts[: len(conf_prefix_parts)] == conf_prefix_parts
                ):
                    sub_path = Path(*doc_path.parts[len(conf_prefix_parts) :])
                elif len(doc_path.parts) > 1 and doc_path.parts[0] in ("docs", "doc"):
                    sub_path = Path(*doc_path.parts[1:])
                else:
                    sub_path = doc_path

                dest_file = docs_src / sub_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(doc.transformed_content, encoding="utf-8")

            # Check theme availability and place conf.py directly at docs_src / conf.py
            theme_status = "INSTALLED"
            for conf_path_str, conf_code in report.generated_sphinx_files.items():
                conf_dest = docs_src / "conf.py"
                conf_dest.parent.mkdir(parents=True, exist_ok=True)

                final_conf = conf_code
                theme_match = re.search(
                    r"html_theme\s*=\s*['\"]([^'\"]+)['\"]", conf_code
                )
                if theme_match:
                    target_theme = theme_match.group(1)
                    if target_theme not in (
                        "alabaster",
                        "default",
                        "classic",
                        "sphinxdoc",
                        "scrolls",
                        "agogo",
                        "traditional",
                        "nature",
                        "haiku",
                        "pyramid",
                        "bizstyle",
                    ):
                        theme_mod = target_theme.replace("-", "_")
                        if importlib.util.find_spec(theme_mod) is None:
                            theme_status = f"THEME_UNAVAILABLE:{target_theme}"
                            fallback_theme = (
                                "furo"
                                if importlib.util.find_spec("furo") is not None
                                else "alabaster"
                            )
                            final_conf = re.sub(
                                r"html_theme\s*=\s*['\"][^'\"]+['\"]",
                                f'html_theme = "{fallback_theme}"',
                                final_conf,
                            )
                            final_conf = final_conf.replace(
                                f'"{theme_mod}",', ""
                            ).replace(f"'{theme_mod}',", "")

                # Ensure sphinx_immaterial disables remote Google font downloads in sandbox builds
                if "sphinx_immaterial" in final_conf:
                    if "html_theme_options" in final_conf:
                        if (
                            "'font': False" not in final_conf
                            and '"font": False' not in final_conf
                        ):
                            final_conf = re.sub(
                                r"html_theme_options\s*=\s*\{",
                                "html_theme_options = {'font': False, ",
                                final_conf,
                                count=1,
                            )
                    else:
                        final_conf += "\nhtml_theme_options = {'font': False}\n"

                conf_dest.write_text(final_conf, encoding="utf-8")

            # Execute real sphinx.cmd.build
            cmd = [sys.executable, "-m", "sphinx.cmd.build", "-b", "html"]
            if strict_warnings:
                cmd.append("-W")
            cmd.extend([str(docs_src), str(docs_out)])

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                )
                combined_output = f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

                # Parse stderr/stdout for Sphinx warnings
                warnings: List[str] = []
                for line in (proc.stdout + "\n" + proc.stderr).splitlines():
                    if "WARNING:" in line or "warning:" in line.lower():
                        if line.strip() not in warnings:
                            warnings.append(line.strip())

                if proc.returncode == 0:
                    return True, combined_output, warnings, theme_status
                else:
                    return False, combined_output, warnings, theme_status
            except Exception as ex:
                return False, f"Sphinx execution error: {str(ex)}", [], theme_status
