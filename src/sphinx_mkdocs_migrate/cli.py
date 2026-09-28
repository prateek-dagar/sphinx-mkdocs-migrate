"""Command-line interface for deterministic MkDocs-to-Sphinx migration."""
import sys
import json
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from .analyzer.project import ProjectAnalyzer
from .planner.planner import MigrationPlanner
from .transformer.engine import TransformationEngine
from .validator.verifier import TransformationValidator

console = Console()

@click.group()
@click.version_option(version="0.1.0b1", prog_name="sphinx-migrate")
def main():
    """Deterministic, version-aware CLI toolkit for migrating MkDocs to Sphinx + MyST."""
    pass

@main.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path), default=".")
@click.option("--json-output", "json_out", is_flag=True, default=False, help="Output factual analysis report as JSON.")
def analyze(project_path: Path, json_out: bool):
    """Factual inspection of an MkDocs documentation project."""
    analyzer = ProjectAnalyzer(project_path)
    report = analyzer.analyze()

    if json_out:
        sys.stdout.write(json.dumps(report.model_dump(), indent=2, default=str) + "\n")
        return

    console.print(f"[bold blue]Inspecting MkDocs project:[/bold blue] {project_path.resolve()}")
    console.print()

    table = Table(title="Migration Subsystems", show_header=True, header_style="bold magenta")
    table.add_column("Subsystem", style="cyan", width=24)
    table.add_column("Status", width=16)
    table.add_column("Details")

    for sub in report.subsystem_summaries:
        status_style = "green" if sub.status in ("PRESERVED", "AUTOMATIC") else ("yellow" if sub.status == "REVIEW" else "red")
        table.add_row(sub.name, f"[{status_style}]{sub.status}[/{status_style}]", sub.details)

    console.print(table)
    console.print()

    if report.migration_requirements:
        req_table = Table(title="Derived Migration Requirements", show_header=True, header_style="bold cyan")
        req_table.add_column("Category", width=18)
        req_table.add_column("Disposition", width=22)
        req_table.add_column("Source Construct", width=26)
        req_table.add_column("Required Outcome")

        for req in report.migration_requirements:
            disp_style = "green" if req.disposition.value in ("PRESERVE", "GENERATE") else ("yellow" if req.disposition.value == "TRANSFORM" else "blue")
            req_table.add_row(
                req.category.value,
                f"[{disp_style}]{req.disposition.value}[/{disp_style}]",
                req.source_construct,
                req.required_outcome
            )

        console.print(req_table)
        console.print()

@main.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path), default=".")
@click.option("--output-json", "output_json_path", type=click.Path(dir_okay=False, writable=True, path_type=Path), default=None, help="Write canonical machine-readable migration plan JSON to file.")
@click.option("--json-output", "json_stdout", is_flag=True, default=False, help="Print canonical machine-readable migration plan JSON to stdout.")
def plan(project_path: Path, output_json_path: Optional[Path], json_stdout: bool):
    """Generates a deterministic, read-only MigrationPlan without mutating source files."""
    planner = MigrationPlanner(project_path)
    plan = planner.create_plan()

    if output_json_path:
        output_json_path.write_text(json.dumps(plan.canonical_dict(), indent=2, default=str), encoding="utf-8")
        console.print(f"[bold green]✔ Plan exported to:[/bold green] {output_json_path.resolve()}")

    if json_stdout:
        sys.stdout.write(json.dumps(plan.canonical_dict(), indent=2, default=str) + "\n")
        return

    console.print(f"[bold blue]Generating Migration Plan for:[/bold blue] {project_path.resolve()}")
    console.print()

    inv_table = Table(title="Construct Action Inventory", show_header=True, header_style="bold cyan")
    inv_table.add_column("Classification", width=16)
    inv_table.add_column("Count", justify="right", width=10)
    inv_table.add_column("Description")

    inv_table.add_row("[green]TRANSFORM[/green]", str(plan.summary.transform_count), "Deterministic MyST / Sphinx syntax conversions")
    inv_table.add_row("[blue]PRESERVE[/blue]", str(plan.summary.preserve_count), "Standard Markdown / links preserved as-is")
    inv_table.add_row("[yellow]MANUAL[/yellow]", str(plan.summary.manual_count), "Requires developer review (e.g. mkdocstrings / complex macros)")
    inv_table.add_row("[red]UNSUPPORTED[/red]", str(plan.summary.unsupported_count), "No direct Sphinx equivalent")
    console.print(inv_table)
    console.print()

    ext_items = [r for r in plan.requirements if r.kind == "extension"]
    ext_table = Table(title="Required Sphinx Extensions", show_header=True, header_style="bold green")
    ext_table.add_column("Extension Name", style="bold green", width=28)
    ext_table.add_column("Provenance", width=22)
    ext_table.add_column("Trigger Sources", justify="right", width=16)
    ext_table.add_column("Rationale")

    for r in ext_items:
        ext_table.add_row(r.name, r.provenance.value, str(len(r.sources)), r.rationale)

    console.print(ext_table)
    console.print()

    pkg_items = [r for r in plan.requirements if r.kind == "package"]
    pkg_table = Table(title="Required Python Packages", show_header=True, header_style="bold yellow")
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
        console.print(f"  • Theme: [magenta]{cfg.theme.source_theme}[/magenta] -> [bold green]{target_str}[/bold green] ({cfg.theme.rationale})")
        console.print(f"  • Enabled MyST Extensions: {', '.join(cfg.myst_enable_extensions)}")
        console.print(f"  • Plan Canonical Hash: [dim]{plan.canonical_hash()[:16]}[/dim]")
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
                f"{item.source_file}:{item.line_number}",
                item.construct_type,
                desc
            )
        console.print(manual_table)
        console.print()

    console.print("[dim]Plan generated deterministically. No disk changes were applied.[/dim]")
    console.print()

@main.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path), default=".")
@click.option("--apply", "write_to_disk", is_flag=True, default=False, help="Write transformed files and conf.py to disk.")
@click.option("--force-conf", "overwrite_conf", is_flag=True, default=False, help="Overwrite existing conflicting conf.py if present.")
@click.option("--diff", "show_diff", is_flag=True, default=False, help="Display unified diff of document transformations.")
@click.option("--validate/--no-validate", "run_validation", default=True, help="Validate transformed Markdown structure and Sphinx config.")
@click.option("--build/--no-build", "run_sphinx_build", default=True, help="Run an actual isolated Sphinx HTML build during validation.")
@click.option("--strict", "strict_warnings", is_flag=True, default=False, help="Fail validation if Sphinx produces any warnings (-W).")
def migrate(project_path: Path, write_to_disk: bool, overwrite_conf: bool, show_diff: bool, run_validation: bool, run_sphinx_build: bool, strict_warnings: bool):
    """Executes deterministic MyST transformation, Sphinx scaffolding, and validation."""
    mode_str = "[bold green]APPLYING[/bold green]" if write_to_disk else "[bold cyan]DRY-RUN TRANSFORMATION[/bold cyan]"
    console.print(f"{mode_str} for: {project_path.resolve()}")
    console.print()

    # 1. Generate plan
    planner = MigrationPlanner(project_path)
    plan = planner.create_plan()

    # 2. Execute Transformation
    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=write_to_disk, overwrite_conf=overwrite_conf)

    res_table = Table(title="Document Transformations", show_header=True, header_style="bold magenta")
    res_table.add_column("Document", style="cyan", width=30)
    res_table.add_column("Transforms Applied", justify="right", width=20)
    res_table.add_column("Status", width=18)

    for doc in report.transformed_documents:
        status_color = "green" if doc.status.value == "APPLIED" else ("yellow" if doc.status.value == "MANUAL_REQUIRED" else "blue")
        res_table.add_row(doc.source_file, str(doc.transforms_applied), f"[{status_color}]{doc.status.value}[/{status_color}]")

    console.print(res_table)
    console.print()

    # Report conf.py status
    if report.conf_py_status.value == "CONFLICT":
        console.print("[bold yellow]conf.py Conflict:[/bold yellow] Existing conf.py on disk differs from planned configuration.")
        if not overwrite_conf:
            console.print("[dim yellow]Preserved existing conf.py on disk. Pass --force-conf to overwrite.[/dim yellow]")
        else:
            console.print("[bold red]Overwrote existing conf.py due to --force-conf flag.[/bold red]")
    elif report.conf_py_status.value == "CREATED":
        console.print("[green]conf.py Scaffolding:[/green] New Sphinx configuration planned/created.")
    elif report.conf_py_status.value == "UNCHANGED":
        console.print("[dim green]conf.py Scaffolding:[/dim green] Existing conf.py on disk is identical to plan.")
    console.print()

    if report.total_stale_actions > 0:
        console.print(f"[bold yellow]Stale Actions Detected:[/bold yellow] {report.total_stale_actions} planned transformation(s) were skipped because source files changed.")
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
            report,
            run_sphinx_build=run_sphinx_build,
            strict_warnings=strict_warnings
        )
        
        if v_report.passed:
            build_str = " (with isolated Sphinx build verified)" if run_sphinx_build else " (structural validation only)"
            console.print(f"[bold green]✔ Validation Passed:[/bold green] All transformed directives and Sphinx conf.py are valid{build_str}.")
            if run_sphinx_build and v_report.sphinx_warning_count > 0:
                console.print(f"[dim yellow]Sphinx Warnings ({v_report.sphinx_warning_count}): Run with --strict to treat as errors.[/dim yellow]")
        else:
            console.print(f"[bold red]✖ Validation Failed:[/bold red] {v_report.errors_count} error(s) detected.")
            for issue in v_report.issues:
                console.print(f"  • [{issue.severity.value}] {issue.file_path}:{issue.line_number or ''} - {issue.message}")
        console.print()

    console.print("[bold green]Transformation Execution Complete:[/bold green]")
    console.print(f"  • Documents Examined: {report.documents_examined}")
    console.print(f"  • Documents Changed: {report.documents_changed}")
    console.print(f"  • Files Written to Disk: {report.files_written_to_disk}")
    console.print(f"  • Total Transformations Executed: {report.total_transforms_executed}")
    console.print(f"  • Stale Transformations Skipped: {report.total_stale_actions}")
    console.print()
    if not write_to_disk:
        console.print("[dim]Dry-run mode: files were not modified. Pass --apply to write changes to disk.[/dim]")
        console.print()

@main.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path), default=".")
@click.option("--build/--no-build", "run_sphinx_build", default=True, help="Run an actual isolated Sphinx HTML build during validation.")
@click.option("--strict", "strict_warnings", is_flag=True, default=False, help="Fail validation if Sphinx produces any warnings (-W).")
@click.option("--show-warnings", "show_warnings", is_flag=True, default=False, help="Display detailed Sphinx warnings in validation report.")
def validate(project_path: Path, run_sphinx_build: bool, strict_warnings: bool, show_warnings: bool):
    """Validates existing or migrated Sphinx configuration and documents."""
    console.print(f"[bold blue]Validating documentation structure for:[/bold blue] {project_path.resolve()}")
    console.print()
    planner = MigrationPlanner(project_path)
    plan = planner.create_plan()
    engine = TransformationEngine(plan)
    report = engine.execute(write_to_disk=False)
    validator = TransformationValidator()
    v_report = validator.validate_transformation_report(report, run_sphinx_build=run_sphinx_build, strict_warnings=strict_warnings)
    
    if v_report.passed:
        build_str = " (with isolated Sphinx build verified)" if run_sphinx_build else " (structural validation only)"
        console.print(f"[bold green]✔ Validation Passed:[/bold green] All directives and conf.py are valid{build_str}.")
        if run_sphinx_build and v_report.sphinx_warning_count > 0:
            console.print(f"[dim yellow]Sphinx Warnings ({v_report.sphinx_warning_count}): Run with --strict to treat as errors.[/dim yellow]")
            if show_warnings:
                for idx, w in enumerate(v_report.sphinx_warnings, 1):
                    console.print(f"  [yellow]•[/yellow] [dim]{w.strip()}[/dim]")
    else:
        console.print(f"[bold red]✖ Validation Failed:[/bold red] {v_report.errors_count} error(s) detected.")
        for issue in v_report.issues:
            console.print(f"  • [{issue.severity.value}] {issue.file_path}:{issue.line_number or ''} - {issue.message}")
        sys.exit(1)

if __name__ == "__main__":
    main()
