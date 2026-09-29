"""Command-line interface for deterministic MkDocs-to-Sphinx migration."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from .analyzer.models import Classification
from .analyzer.project import ProjectAnalyzer
from .planner.planner import MigrationPlanner
from .transformer.engine import TransformationEngine
from .validator.verifier import TransformationValidator
from . import __version__

console = Console()


def _normalize_module_name(pkg_name: str) -> str:
    """Normalize a Python package name to its top-level importable module name."""
    mapping = {
        "myst-parser": "myst_parser",
        "sphinx-immaterial": "sphinx_immaterial",
        "sphinx-design": "sphinx_design",
        "sphinx-copybutton": "sphinx_copybutton",
        "sphinx-rtd-theme": "sphinx_rtd_theme",
        "sphinxcontrib-mermaid": "sphinxcontrib.mermaid",
        "mkdocs-material": "material",
    }
    m = re.match(r"^([a-zA-Z0-9_\-\.]+)", pkg_name)
    base = (
        m.group(1).lower().replace("_", "-")
        if m
        else pkg_name.lower().replace("_", "-")
    )
    return mapping.get(base, base.replace("-", "_"))


def _get_missing_sphinx_packages(candidates: List[str]) -> List[str]:
    """Return candidates that are not found in the current Python environment."""
    missing: List[str] = []
    for pkg in candidates:
        mod = _normalize_module_name(pkg)
        try:
            if importlib.util.find_spec(mod) is None:
                missing.append(pkg)
        except (ModuleNotFoundError, ValueError):
            missing.append(pkg)
    return missing


def _get_installed_mkdocs_packages(candidates: List[str]) -> List[str]:
    """Return MkDocs packages that are currently installed in the environment."""
    installed: List[str] = []
    for pkg in candidates:
        mod = _normalize_module_name(pkg)
        try:
            if importlib.util.find_spec(mod) is not None:
                installed.append(pkg)
        except (ModuleNotFoundError, ValueError):
            pass
    return installed


def _is_interactive() -> bool:
    """Return whether the current session is running in an interactive terminal."""
    return sys.stdin.isatty()


def _collect_manual_review_resolutions(
    plan,
    project_root: Path,
) -> Dict[str, str]:
    """Interactively prompt user to resolve constructs requiring manual review.

    Returns:
        Dict mapping action_id -> custom replacement text.
    """
    manual_actions = [
        act
        for act in plan.document_actions
        if act.classification == Classification.MANUAL
    ]
    if not manual_actions:
        return {}

    manual_actions.sort(key=lambda a: (a.source_file, a.start_line))
    total = len(manual_actions)

    console.print(
        f"\n[bold yellow]Constructs Requiring Manual Review ({total}):[/bold yellow]"
    )
    console.print(
        "[dim]You can review each construct to keep it as-is, comment it out, or enter a custom MyST replacement.[/dim]\n"
    )

    overrides: Dict[str, str] = {}
    for idx, act in enumerate(manual_actions, 1):
        src_path = project_root / act.source_file
        snippet = ""
        if src_path.exists():
            try:
                lines = src_path.read_text(encoding="utf-8").splitlines(keepends=True)
                start_idx = max(0, act.start_line - 1)
                end_idx = min(len(lines), act.end_line)
                snippet = "".join(lines[start_idx:end_idx])
            except Exception:
                snippet = act.description
        else:
            snippet = act.description

        console.print(
            f"[bold cyan]Item {idx}/{total}:[/bold cyan] [bold]{act.source_file}:{act.start_line}-{act.end_line}[/bold]"
        )
        console.print(
            f"  • Construct: [magenta]{act.source_kind.value}[/magenta] ([dim]{act.rule_id}[/dim])"
        )
        if act.manual_instruction:
            console.print(f"  • Instruction: [yellow]{act.manual_instruction}[/yellow]")
        console.print()

        if snippet.strip():
            console.print(
                Syntax(
                    snippet.strip(),
                    "markdown",
                    line_numbers=True,
                    start_line=act.start_line,
                )
            )
            console.print()

        console.print("  [1] Keep original content (safe, default)")
        console.print(
            f"  [2] Comment out block (<!-- MANUAL_REVIEW: {act.source_kind.value} -->)"
        )
        console.print("  [3] Enter custom replacement text")
        console.print("  [s] Skip remaining and keep original for all")
        console.print()

        choice = Prompt.ask(
            "Choose action",
            choices=["1", "2", "3", "s"],
            default="1",
        )

        if choice == "1":
            console.print("[dim]Kept original content.[/dim]\n")
        elif choice == "2":
            comment_text = (
                f"<!-- MANUAL_REVIEW: {act.source_kind.value}\n"
                f"{snippet.rstrip()}\n"
                f"-->\n"
            )
            overrides[act.action_id] = comment_text
            console.print("[green]Marked block as commented out.[/green]\n")
        elif choice == "3":
            custom_text = Prompt.ask(
                "Enter custom replacement text (use \\n for newlines)",
                default="",
            )
            if not custom_text.strip():
                if Confirm.ask("Empty replacement: delete block?", default=False):
                    overrides[act.action_id] = ""
                    console.print("[green]Block marked for deletion.[/green]\n")
                else:
                    console.print("[dim]Kept original content.[/dim]\n")
            else:
                custom_text = custom_text.replace(r"\n", "\n")
                if not custom_text.endswith("\n"):
                    custom_text += "\n"
                overrides[act.action_id] = custom_text
                console.print("[green]Custom replacement saved.[/green]\n")
        elif choice == "s":
            console.print(
                "[dim]Skipping remaining items; keeping original content.[/dim]\n"
            )
            break

    return overrides


@click.group()
@click.version_option(version=__version__, prog_name="sphinx-migrate")
def main():
    """Deterministic, version-aware CLI toolkit for migrating MkDocs to Sphinx + MyST."""
    pass


@main.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--json-output",
    "json_out",
    is_flag=True,
    default=False,
    help="Output factual analysis report as JSON.",
)
def analyze(project_path: Path, json_out: bool):
    """Factual inspection of an MkDocs documentation project."""
    analyzer = ProjectAnalyzer(project_path)
    report = analyzer.analyze()

    if json_out:
        sys.stdout.write(json.dumps(report.model_dump(), indent=2, default=str) + "\n")
        return

    console.print(
        f"[bold blue]Inspecting MkDocs project:[/bold blue] {project_path.resolve()}"
    )
    console.print()

    table = Table(
        title="Migration Subsystems", show_header=True, header_style="bold magenta"
    )
    table.add_column("Subsystem", style="cyan", width=24)
    table.add_column("Status", width=16)
    table.add_column("Details")

    for sub in report.subsystem_summaries:
        status_style = (
            "green"
            if sub.status in ("PRESERVED", "AUTOMATIC")
            else ("yellow" if sub.status == "REVIEW" else "red")
        )
        table.add_row(
            sub.name, f"[{status_style}]{sub.status}[/{status_style}]", sub.details
        )

    console.print(table)
    console.print()

    if report.migration_requirements:
        req_table = Table(
            title="Derived Migration Requirements",
            show_header=True,
            header_style="bold cyan",
        )
        req_table.add_column("Category", width=18)
        req_table.add_column("Disposition", width=22)
        req_table.add_column("Source Construct", width=26)
        req_table.add_column("Required Outcome")

        for req in report.migration_requirements:
            disp_style = (
                "green"
                if req.disposition.value in ("PRESERVE", "GENERATE")
                else ("yellow" if req.disposition.value == "TRANSFORM" else "blue")
            )
            req_table.add_row(
                req.category.value,
                f"[{disp_style}]{req.disposition.value}[/{disp_style}]",
                req.source_construct,
                req.required_outcome,
            )

        console.print(req_table)
        console.print()


@main.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--output-json",
    "output_json_path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Write canonical machine-readable migration plan JSON to file.",
)
@click.option(
    "--json-output",
    "json_stdout",
    is_flag=True,
    default=False,
    help="Print canonical machine-readable migration plan JSON to stdout.",
)
def plan(project_path: Path, output_json_path: Optional[Path], json_stdout: bool):
    """Generates a deterministic, read-only MigrationPlan without mutating source files."""
    planner = MigrationPlanner(project_path)
    plan = planner.create_plan()

    if output_json_path:
        output_json_path.write_text(
            json.dumps(plan.canonical_dict(), indent=2, default=str), encoding="utf-8"
        )
        console.print(
            f"[bold green]✔ Plan exported to:[/bold green] {output_json_path.resolve()}"
        )

    if json_stdout:
        sys.stdout.write(
            json.dumps(plan.canonical_dict(), indent=2, default=str) + "\n"
        )
        return

    console.print(
        f"[bold blue]Generating Migration Plan for:[/bold blue] {project_path.resolve()}"
    )
    console.print()

    inv_table = Table(
        title="Construct Action Inventory", show_header=True, header_style="bold cyan"
    )
    inv_table.add_column("Classification", width=16)
    inv_table.add_column("Count", justify="right", width=10)
    inv_table.add_column("Description")

    inv_table.add_row(
        "[green]TRANSFORM[/green]",
        str(plan.summary.transform_count),
        "Deterministic MyST / Sphinx syntax conversions",
    )
    inv_table.add_row(
        "[blue]PRESERVE[/blue]",
        str(plan.summary.preserve_count),
        "Standard Markdown / links preserved as-is",
    )
    inv_table.add_row(
        "[yellow]MANUAL[/yellow]",
        str(plan.summary.manual_count),
        "Requires developer review (e.g. mkdocstrings / complex macros)",
    )
    inv_table.add_row(
        "[red]UNSUPPORTED[/red]",
        str(plan.summary.unsupported_count),
        "No direct Sphinx equivalent",
    )
    console.print(inv_table)
    console.print()

    ext_items = [r for r in plan.requirements if r.kind == "extension"]
    ext_table = Table(
        title="Required Sphinx Extensions", show_header=True, header_style="bold green"
    )
    ext_table.add_column("Extension Name", style="bold green", width=28)
    ext_table.add_column("Provenance", width=22)
    ext_table.add_column("Trigger Sources", justify="right", width=16)
    ext_table.add_column("Rationale")

    for r in ext_items:
        ext_table.add_row(r.name, r.provenance.value, str(len(r.sources)), r.rationale)

    console.print(ext_table)
    console.print()

    pkg_items = [r for r in plan.requirements if r.kind == "package"]
    pkg_table = Table(
        title="Required Python Packages", show_header=True, header_style="bold yellow"
    )
    pkg_table.add_column("Package Spec", style="bold yellow", width=28)
    pkg_table.add_column("Provenance", width=22)
    pkg_table.add_column("Trigger Sources", justify="right", width=16)
    pkg_table.add_column("Rationale")

    for r in pkg_items:
        pkg_table.add_row(r.name, r.provenance.value, str(len(r.sources)), r.rationale)

    console.print(pkg_table)
    console.print()

    if plan.proposed_sphinx_config:
        cfg = plan.proposed_sphinx_config
        target_str = cfg.theme.target_theme or "MANUAL REVIEW"
        console.print("[bold cyan]Sphinx Configuration Proposal:[/bold cyan]")
        console.print(
            f"  • Theme: [magenta]{cfg.theme.source_theme}[/magenta] -> [bold green]{target_str}[/bold green] ({cfg.theme.rationale})"
        )
        console.print(
            f"  • Enabled MyST Extensions: {', '.join(cfg.myst_enable_extensions)}"
        )
        console.print(
            f"  • Plan Canonical Hash: [dim]{plan.canonical_hash()[:16]}[/dim]"
        )
        console.print()

    if plan.manual_action_items:
        console.print("[bold yellow]Actionable Manual Review Items:[/bold yellow]")
        manual_table = Table(show_header=True, header_style="bold yellow")
        manual_table.add_column("Location", style="cyan", width=26)
        manual_table.add_column("Construct", style="magenta", width=18)
        manual_table.add_column("Instruction & Rationale")

        for item in plan.manual_action_items:
            desc = f"[bold]{item.instruction}[/bold] - [dim]{item.rationale}[/dim]"
            manual_table.add_row(
                f"{item.source_file}:{item.line_number}", item.construct_type, desc
            )
        console.print(manual_table)
        console.print()

    if plan.obsolete_files:
        console.print("[bold yellow]Obsolete MkDocs Files to Remove:[/bold yellow]")
        for f in plan.obsolete_files:
            console.print(f"  • [yellow]{f}[/yellow]")
        console.print()

    console.print(
        "[dim]Plan generated deterministically. No disk changes were applied.[/dim]"
    )
    console.print()


@main.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--apply",
    "write_to_disk",
    is_flag=True,
    default=False,
    help="Write transformed files and conf.py to disk.",
)
@click.option(
    "--yes",
    "-y",
    "auto_approve",
    is_flag=True,
    default=False,
    help="Automatically confirm prompts and apply migration without interactive confirmation.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    "interactive",
    default=None,
    help="Prompt interactively to resolve constructs requiring manual review.",
)
@click.option(
    "--install-deps/--no-install-deps",
    "install_deps",
    default=None,
    help="Automatically install (or skip installing) missing Sphinx dependencies in current environment.",
)
@click.option(
    "--uninstall-mkdocs/--no-uninstall-mkdocs",
    "uninstall_mkdocs",
    default=None,
    help="Automatically uninstall (or skip uninstalling) obsolete MkDocs dependencies from current environment.",
)
@click.option(
    "--force-conf",
    "overwrite_conf",
    is_flag=True,
    default=False,
    help="Overwrite existing conflicting conf.py if present.",
)
@click.option(
    "--diff",
    "show_diff",
    is_flag=True,
    default=False,
    help="Display unified diff of document transformations.",
)
@click.option(
    "--validate/--no-validate",
    "run_validation",
    default=True,
    help="Validate transformed Markdown structure and Sphinx config.",
)
@click.option(
    "--build/--no-build",
    "run_sphinx_build",
    default=True,
    help="Run an actual isolated Sphinx HTML build during validation.",
)
@click.option(
    "--strict",
    "strict_warnings",
    is_flag=True,
    default=False,
    help="Fail validation if Sphinx produces any warnings (-W).",
)
def migrate(
    project_path: Path,
    write_to_disk: bool,
    auto_approve: bool,
    interactive: Optional[bool],
    install_deps: Optional[bool],
    uninstall_mkdocs: Optional[bool],
    overwrite_conf: bool,
    show_diff: bool,
    run_validation: bool,
    run_sphinx_build: bool,
    strict_warnings: bool,
):
    """Executes deterministic MyST transformation, Sphinx scaffolding, and validation."""
    mode_str = (
        "[bold green]APPLYING[/bold green]"
        if write_to_disk
        else "[bold cyan]DRY-RUN TRANSFORMATION[/bold cyan]"
    )
    console.print(f"{mode_str} for: {project_path.resolve()}")
    console.print()

    # 1. Generate plan
    planner = MigrationPlanner(project_path)
    plan = planner.create_plan()

    # Pre-flight check & interactive confirmation
    to_add: List[str] = (
        list(plan.dependency_analysis.suggested_packages_to_add)
        if plan.dependency_analysis
        else []
    )
    if plan.documentation_plan:
        for req_pkg in plan.documentation_plan.required_packages or []:
            to_add.append(req_pkg)
        if "sphinx_copybutton" in (plan.documentation_plan.required_extensions or []):
            to_add.append("sphinx-copybutton")
    to_add = sorted(list(dict.fromkeys(to_add)))

    to_remove: List[str] = list(plan.packages_to_remove or [])
    if plan.dependency_analysis:
        to_remove.extend(plan.dependency_analysis.detected_packages_to_remove)
    to_remove = sorted(list(dict.fromkeys(to_remove)))

    if write_to_disk:
        console.print("[bold]Migration Pre-flight Check:[/bold]")
        console.print(f"  • Planned transformations: {len(plan.document_actions)}")
        if to_add:
            console.print(
                f"  • Sphinx dependencies to add: [green]{', '.join(to_add)}[/green]"
            )
        if to_remove:
            console.print(
                f"  • MkDocs dependencies to remove: [yellow]{', '.join(to_remove)}[/yellow]"
            )
        console.print()

        if not auto_approve and _is_interactive():
            if not Confirm.ask("Apply migration changes to disk?", default=True):
                console.print("[yellow]Migration cancelled by user.[/yellow]")
                return

    # 2. Collect manual review resolutions if interactive
    manual_overrides: Dict[str, str] = {}
    has_manual = any(
        act.classification == Classification.MANUAL for act in plan.document_actions
    )
    should_prompt_manual = (
        has_manual
        and not auto_approve
        and (
            interactive is True
            or (interactive is None and write_to_disk and _is_interactive())
        )
    )
    if should_prompt_manual:
        manual_overrides = _collect_manual_review_resolutions(plan, project_path)

    # 3. Execute Transformation
    engine = TransformationEngine(plan, manual_overrides=manual_overrides)
    report = engine.execute(write_to_disk=write_to_disk, overwrite_conf=overwrite_conf)

    res_table = Table(
        title="Document Transformations", show_header=True, header_style="bold magenta"
    )
    res_table.add_column("Document", style="cyan", width=30)
    res_table.add_column("Transforms Applied", justify="right", width=20)
    res_table.add_column("Status", width=18)

    for doc in report.transformed_documents:
        status_color = (
            "green"
            if doc.status.value == "APPLIED"
            else ("yellow" if doc.status.value == "MANUAL_REQUIRED" else "blue")
        )
        res_table.add_row(
            doc.source_file,
            str(doc.transforms_applied),
            f"[{status_color}]{doc.status.value}[/{status_color}]",
        )

    console.print(res_table)
    console.print()

    # Report conf.py status
    if report.conf_py_status.value == "CONFLICT":
        console.print(
            "[bold yellow]conf.py Conflict:[/bold yellow] Existing conf.py on disk differs from planned configuration."
        )
        if not overwrite_conf:
            console.print(
                "[dim yellow]Preserved existing conf.py on disk. Pass --force-conf to overwrite.[/dim yellow]"
            )
        else:
            console.print(
                "[bold red]Overwrote existing conf.py due to --force-conf flag.[/bold red]"
            )
    elif report.conf_py_status.value == "CREATED":
        console.print(
            "[green]conf.py Scaffolding:[/green] New Sphinx configuration planned/created."
        )
    elif report.conf_py_status.value == "UNCHANGED":
        console.print(
            "[dim green]conf.py Scaffolding:[/dim green] Existing conf.py on disk is identical to plan."
        )
    console.print()

    if report.total_stale_actions > 0:
        console.print(
            f"[bold yellow]Stale Actions Detected:[/bold yellow] {report.total_stale_actions} planned transformation(s) were skipped because source files changed."
        )
        for doc in report.transformed_documents:
            for detail in doc.stale_action_details:
                console.print(f"  • [yellow]{detail}[/yellow]")
        console.print()

    if show_diff:
        for doc in report.transformed_documents:
            if doc.diff:
                console.print(f"[bold yellow]Diff for {doc.source_file}:[/bold yellow]")
                syntax = Syntax(doc.diff, "diff", theme="monokai", line_numbers=False)
                console.print(syntax)
                console.print()

    # 3. Validation Step
    if run_validation:
        validator = TransformationValidator()
        v_report = validator.validate_transformation_report(
            report, run_sphinx_build=run_sphinx_build, strict_warnings=strict_warnings
        )

        if v_report.passed:
            build_str = (
                " (with isolated Sphinx build verified)"
                if run_sphinx_build
                else " (structural validation only)"
            )
            console.print(
                f"[bold green]✔ Validation Passed:[/bold green] All transformed directives and Sphinx conf.py are valid{build_str}."
            )
            if run_sphinx_build and v_report.sphinx_warning_count > 0:
                console.print(
                    f"[dim yellow]Sphinx Warnings ({v_report.sphinx_warning_count}): Run with --strict to treat as errors.[/dim yellow]"
                )
        else:
            console.print(
                f"[bold red]✖ Validation Failed:[/bold red] {v_report.errors_count} error(s) detected."
            )
            for issue in v_report.issues:
                console.print(
                    f"  • [{issue.severity.value}] {issue.file_path}:{issue.line_number or ''} - {issue.message}"
                )
        console.print()

    console.print("[bold green]Transformation Execution Complete:[/bold green]")
    console.print(f"  • Documents Examined: {report.documents_examined}")
    console.print(f"  • Documents Changed: {report.documents_changed}")
    console.print(f"  • Files Written to Disk: {report.files_written_to_disk}")
    console.print(
        f"  • Total Transformations Executed: {report.total_transforms_executed}"
    )
    console.print(f"  • Stale Transformations Skipped: {report.total_stale_actions}")
    if report.cleaned_files:
        console.print(f"  • Obsolete MkDocs Files Removed: {len(report.cleaned_files)}")
        for cf in report.cleaned_files:
            console.print(f"      - [yellow]{cf}[/yellow]")
    console.print()

    if write_to_disk:
        # Check missing Sphinx packages in current environment
        missing_sphinx = _get_missing_sphinx_packages(to_add)
        if missing_sphinx:
            console.print(
                "[bold yellow]Notice: Missing Sphinx dependencies in current environment:[/bold yellow]"
            )
            for p in missing_sphinx:
                console.print(f"  • [yellow]{p}[/yellow]")
            console.print()

            do_install = False
            if install_deps is True:
                do_install = True
            elif install_deps is None and not auto_approve and _is_interactive():
                do_install = Confirm.ask(
                    f"Install {len(missing_sphinx)} missing Sphinx dependencies into current environment?",
                    default=True,
                )

            if do_install:
                console.print(
                    f"[bold cyan]Installing {', '.join(missing_sphinx)}...[/bold cyan]"
                )
                res = subprocess.run(
                    [sys.executable, "-m", "pip", "install", *missing_sphinx]
                )
                if res.returncode == 0:
                    console.print(
                        "[bold green]✔ Dependencies installed successfully.[/bold green]\n"
                    )
                else:
                    console.print(
                        "[bold red]✖ Failed to install dependencies via pip.[/bold red]\n"
                    )
            else:
                console.print(
                    f"[dim]To install manually: [bold]pip install {' '.join(missing_sphinx)}[/bold][/dim]\n"
                )

        # Check installed obsolete MkDocs packages in current environment
        installed_mkdocs = _get_installed_mkdocs_packages(to_remove)
        if installed_mkdocs:
            console.print(
                "[bold yellow]Notice: Found obsolete MkDocs dependencies in current environment:[/bold yellow]"
            )
            for p in installed_mkdocs:
                console.print(f"  • [yellow]{p}[/yellow]")
            console.print()

            do_uninstall = False
            if uninstall_mkdocs is True:
                do_uninstall = True
            elif uninstall_mkdocs is None and not auto_approve and _is_interactive():
                do_uninstall = Confirm.ask(
                    f"Uninstall {len(installed_mkdocs)} obsolete MkDocs dependencies from current environment?",
                    default=False,
                )

            if do_uninstall:
                console.print(
                    f"[bold cyan]Uninstalling {', '.join(installed_mkdocs)}...[/bold cyan]"
                )
                res = subprocess.run(
                    [sys.executable, "-m", "pip", "uninstall", "-y", *installed_mkdocs]
                )
                if res.returncode == 0:
                    console.print(
                        "[bold green]✔ Obsolete MkDocs dependencies uninstalled.[/bold green]\n"
                    )
                else:
                    console.print(
                        "[bold red]✖ Failed to uninstall dependencies via pip.[/bold red]\n"
                    )
            else:
                console.print(
                    f"[dim]To uninstall manually: [bold]pip uninstall -y {' '.join(installed_mkdocs)}[/bold][/dim]\n"
                )
    else:
        console.print(
            "[dim]Dry-run mode: files were not modified. Pass --apply to write changes to disk.[/dim]"
        )
        console.print()


@main.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--build/--no-build",
    "run_sphinx_build",
    default=True,
    help="Run an actual isolated Sphinx HTML build during validation.",
)
@click.option(
    "--strict",
    "strict_warnings",
    is_flag=True,
    default=False,
    help="Fail validation if Sphinx produces any warnings (-W).",
)
@click.option(
    "--show-warnings",
    "show_warnings",
    is_flag=True,
    default=False,
    help="Display detailed Sphinx warnings in validation report.",
)
def validate(
    project_path: Path,
    run_sphinx_build: bool,
    strict_warnings: bool,
    show_warnings: bool,
):
    """Validates existing or migrated Sphinx configuration and documents."""
    console.print(
        f"[bold blue]Validating documentation structure for:[/bold blue] {project_path.resolve()}"
    )
    console.print()
    planner = MigrationPlanner(project_path)
    plan = planner.create_plan()
    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(
        report, run_sphinx_build=run_sphinx_build, strict_warnings=strict_warnings
    )

    if v_report.passed:
        build_str = (
            " (with isolated Sphinx build verified)"
            if run_sphinx_build
            else " (structural validation only)"
        )
        console.print(
            f"[bold green]✔ Validation Passed:[/bold green] All directives and conf.py are valid{build_str}."
        )
        if run_sphinx_build and v_report.sphinx_warning_count > 0:
            console.print(
                f"[dim yellow]Sphinx Warnings ({v_report.sphinx_warning_count}): Run with --strict to treat as errors.[/dim yellow]"
            )
            if show_warnings:
                for idx, w in enumerate(v_report.sphinx_warnings, 1):
                    console.print(f"  [yellow]•[/yellow] [dim]{w.strip()}[/dim]")
    else:
        console.print(
            f"[bold red]✖ Validation Failed:[/bold red] {v_report.errors_count} error(s) detected."
        )
        for issue in v_report.issues:
            console.print(
                f"  • [{issue.severity.value}] {issue.file_path}:{issue.line_number or ''} - {issue.message}"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
