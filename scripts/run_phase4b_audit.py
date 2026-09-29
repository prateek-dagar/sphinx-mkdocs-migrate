#!/usr/bin/env python3
from pathlib import Path
from sphinx_mkdocs_migrate.analyzer.project import ProjectAnalyzer
from sphinx_mkdocs_migrate.planner.planner import MigrationPlanner
from sphinx_mkdocs_migrate.transformer.engine import TransformationEngine
from sphinx_mkdocs_migrate.validator.verifier import TransformationValidator


def run_audit():
    real_repos_dir = Path("scratch/real_repos")
    repos = sorted([d for d in real_repos_dir.iterdir() if d.is_dir()])
    print(f"Starting audit across {len(repos)} real repositories...")

    results = {}
    for repo in repos:
        try:
            analyzer = ProjectAnalyzer(repo)
            report = analyzer.analyze()
            planner = MigrationPlanner(repo)
            plan = planner.create_plan()
            engine = TransformationEngine(plan)
            trans_report = engine.execute(write_to_disk=False)
            validator = TransformationValidator()
            val_report = validator.validate_transformation_report(
                trans_report, run_sphinx_build=True, strict_warnings=False
            )

            err_msg = None
            if val_report.build_output and not val_report.sphinx_build_successful:
                for line in val_report.build_output.splitlines():
                    if any(
                        k in line
                        for k in ("Error", "Exception", "TypeError", "ValueError")
                    ):
                        err_msg = line.strip()

            results[repo.name] = {
                "docs": report.total_markdown_files,
                "actions": len(plan.document_actions),
                "transforms": plan.summary.transform_count,
                "preserve": plan.summary.preserve_count,
                "manual": plan.summary.manual_count,
                "unsupported": len(plan.unsupported_constructs),
                "docs_changed": trans_report.documents_changed,
                "sphinx_success": val_report.sphinx_build_successful,
                "sphinx_warnings": val_report.sphinx_warning_count,
                "root_cause": err_msg,
            }
        except Exception as e:
            results[repo.name] = {"exception": str(e)}

    print("\n" + "=" * 95)
    print(
        f"| {'Repository':<20} | {'Docs':>5} | {'Actions':>7} | {'Trans':>5} | {'Pres':>6} | {'Manual':>6} | {'Sphinx':>7} | {'Warnings':>8} |"
    )
    print("=" * 95)
    for k, v in sorted(results.items()):
        if "exception" in v:
            print(f"| {k:<20} | EXCEPTION: {v['exception']}")
        else:
            status = "PASS" if v["sphinx_success"] else "FAIL"
            print(
                f"| {k:<20} | {v['docs']:>5} | {v['actions']:>7} | {v['transforms']:>5} | {v['preserve']:>6} | {v['manual']:>6} | {status:>7} | {v['sphinx_warnings']:>8} |"
            )
    print("=" * 95)

    print("\n=== ROOT CAUSE BREAKDOWN FOR FAILING BUILDS ===")
    for k, v in sorted(results.items()):
        if not v.get("sphinx_success") and "root_cause" in v:
            print(f"- {k:<20}: {v['root_cause']}")


if __name__ == "__main__":
    run_audit()
