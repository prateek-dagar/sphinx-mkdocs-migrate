from pathlib import Path
from typing import Dict, Set, Any
from sphinx_mkdocs_migrate.analyzer.project import ProjectAnalyzer


def extract_corpus_features():
    real_repos_dir = Path("scratch/real_repos")
    repos = sorted([d for d in real_repos_dir.iterdir() if d.is_dir()])

    print("======================================================================")
    print("     PHASE 4C.4.1: EMPIRICAL CORPUS FEATURE & EXTENSION INVENTORY     ")
    print("======================================================================")
    print(
        f"Auditing {len(repos)} real repositories for MkDocs features, extensions, and plugins...\n"
    )

    all_extensions: Set[str] = set()
    all_plugins: Set[str] = set()
    all_theme_features: Set[str] = set()
    repo_breakdowns: Dict[str, Dict[str, Any]] = {}

    for repo in repos:
        analyzer = ProjectAnalyzer(repo)
        report = analyzer.analyze()
        cfg = report.mkdocs_config

        all_extensions.update(cfg.markdown_extensions)
        all_plugins.update(cfg.plugins)
        all_theme_features.update(cfg.theme_features)

        repo_breakdowns[repo.name] = {
            "theme": cfg.theme_name,
            "theme_features": cfg.theme_features,
            "extensions": cfg.markdown_extensions,
            "plugins": cfg.plugins,
        }

    print("1. EMPIRICALLY OBSERVED MARKDOWN EXTENSIONS across 9 Repositories:")
    for ext in sorted(all_extensions):
        using_repos = [r for r, d in repo_breakdowns.items() if ext in d["extensions"]]
        print(
            f"   • {ext:<35} (used in {len(using_repos)} repos: {', '.join(using_repos)})"
        )

    print("\n2. EMPIRICALLY OBSERVED PLUGINS across 9 Repositories:")
    for plug in sorted(all_plugins):
        using_repos = [r for r, d in repo_breakdowns.items() if plug in d["plugins"]]
        print(
            f"   • {plug:<35} (used in {len(using_repos)} repos: {', '.join(using_repos)})"
        )

    print("\n3. EMPIRICALLY OBSERVED THEME FEATURES across 9 Repositories:")
    for feat in sorted(all_theme_features):
        using_repos = [
            r for r, d in repo_breakdowns.items() if feat in d["theme_features"]
        ]
        print(
            f"   • {feat:<35} (used in {len(using_repos)} repos: {', '.join(using_repos)})"
        )

    print("\n======================================================================")


if __name__ == "__main__":
    extract_corpus_features()
