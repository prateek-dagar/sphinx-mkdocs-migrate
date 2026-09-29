"""Tests for interactive migration confirmation and environment dependency management."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from sphinx_mkdocs_migrate.cli import (
    main,
    _normalize_module_name,
    _get_missing_sphinx_packages,
    _get_installed_mkdocs_packages,
)


def test_normalize_module_name():
    assert _normalize_module_name("sphinx-immaterial") == "sphinx_immaterial"
    assert _normalize_module_name("myst-parser>=2.0.0") == "myst_parser"
    assert _normalize_module_name("mkdocs-material") == "material"
    assert _normalize_module_name("sphinx-design") == "sphinx_design"
    assert _normalize_module_name("custom-pkg") == "custom_pkg"


def test_get_missing_and_installed_packages():
    with patch("importlib.util.find_spec") as mock_find:
        # Simulate sphinx_immaterial installed, sphinx_design missing
        def side_effect(mod):
            if mod == "sphinx_immaterial":
                return MagicMock()
            return None

        mock_find.side_effect = side_effect

        missing = _get_missing_sphinx_packages(["sphinx-immaterial", "sphinx-design"])
        assert missing == ["sphinx-design"]

        installed = _get_installed_mkdocs_packages(
            ["sphinx-immaterial", "sphinx-design"]
        )
        assert installed == ["sphinx-immaterial"]


def test_cli_migrate_dry_run_no_prompts(tmp_path: Path):
    """Dry run should never prompt for confirmation or dependencies."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["migrate", str(tmp_path), "--no-validate"])
    assert result.exit_code == 0
    assert "DRY-RUN TRANSFORMATION" in result.output
    assert "Dry-run mode: files were not modified" in result.output


def test_cli_migrate_apply_auto_approve(tmp_path: Path):
    """Test --apply with -y / auto-approve flag."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    with patch("sphinx_mkdocs_migrate.cli.subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0)
        result = runner.invoke(
            main,
            ["migrate", str(tmp_path), "--apply", "-y", "--no-validate"],
        )
        assert result.exit_code == 0
        assert "Migration Pre-flight Check:" in result.output
        assert "APPLYING" in result.output
        assert (tmp_path / "docs" / "conf.py").exists()
        assert not (tmp_path / "mkdocs.yml").exists()


def test_cli_migrate_apply_cancelled_by_user(tmp_path: Path):
    """Test user rejecting the pre-flight confirmation prompt."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    with patch("sphinx_mkdocs_migrate.cli._is_interactive", return_value=True):
        with patch("sphinx_mkdocs_migrate.cli.Confirm.ask", return_value=False):
            result = runner.invoke(
                main,
                ["migrate", str(tmp_path), "--apply", "--no-validate"],
            )
            assert result.exit_code == 0
            assert "Migration cancelled by user." in result.output
            assert not (tmp_path / "docs" / "conf.py").exists()
            assert (tmp_path / "mkdocs.yml").exists()


def test_cli_migrate_install_and_uninstall_flags(tmp_path: Path):
    """Test --install-deps and --uninstall-mkdocs flags."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Test\ntheme:\n  name: material\n", encoding="utf-8"
    )

    runner = CliRunner()
    with patch(
        "sphinx_mkdocs_migrate.cli._get_missing_sphinx_packages",
        return_value=["sphinx-immaterial"],
    ):
        with patch(
            "sphinx_mkdocs_migrate.cli._get_installed_mkdocs_packages",
            return_value=["mkdocs"],
        ):
            with patch("sphinx_mkdocs_migrate.cli.subprocess.run") as mock_sub:
                mock_sub.return_value = MagicMock(returncode=0)
                result = runner.invoke(
                    main,
                    [
                        "migrate",
                        str(tmp_path),
                        "--apply",
                        "-y",
                        "--install-deps",
                        "--uninstall-mkdocs",
                        "--no-validate",
                    ],
                )
                assert result.exit_code == 0
                assert "Installing sphinx-immaterial..." in result.output
                assert "Uninstalling mkdocs..." in result.output
                assert mock_sub.call_count == 2


def test_cli_migrate_manual_review_choice_1_keep(tmp_path: Path):
    """Test manual review construct with choice 1 (keep original)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# API\n\n::: my_pkg.Client\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["migrate", str(tmp_path), "-i", "--no-validate"],
        input="1\n",
    )
    assert result.exit_code == 0
    assert "Constructs Requiring Manual Review" in result.output
    assert "Kept original content." in result.output


def test_cli_migrate_manual_review_choice_2_comment(tmp_path: Path):
    """Test manual review construct with choice 2 (comment out block)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# API\n\n::: my_pkg.Client\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    with patch("sphinx_mkdocs_migrate.cli._is_interactive", return_value=True):
        result = runner.invoke(
            main,
            ["migrate", str(tmp_path), "--apply", "-i", "--no-validate"],
            input="y\n2\n",
        )
    assert result.exit_code == 0
    assert "Marked block as commented out." in result.output
    migrated_content = (docs_dir / "index.md").read_text(encoding="utf-8")
    assert "<!-- MANUAL_REVIEW: API_DIRECTIVE" in migrated_content
    assert "::: my_pkg.Client" in migrated_content


def test_cli_migrate_manual_review_choice_3_custom_text(tmp_path: Path):
    """Test manual review construct with choice 3 (enter custom replacement text)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# API\n\n::: my_pkg.Client\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    with patch("sphinx_mkdocs_migrate.cli._is_interactive", return_value=True):
        result = runner.invoke(
            main,
            ["migrate", str(tmp_path), "--apply", "-i", "--no-validate"],
            input="y\n3\n```{py:class} my_pkg.Client\\n```\n",
        )
    assert result.exit_code == 0
    assert "Custom replacement saved." in result.output
    migrated_content = (docs_dir / "index.md").read_text(encoding="utf-8")
    assert "```{py:class} my_pkg.Client" in migrated_content
    assert "::: my_pkg.Client" not in migrated_content


def test_cli_migrate_manual_review_skip_remaining(tmp_path: Path):
    """Test choice 's' skips remaining items and keeps original."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text(
        "# API\n\n::: my_pkg.Client\n\n::: my_pkg.Server\n", encoding="utf-8"
    )
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["migrate", str(tmp_path), "-i", "--no-validate"],
        input="s\n",
    )
    assert result.exit_code == 0
    assert "Skipping remaining items; keeping original content." in result.output


def test_cli_migrate_manual_review_auto_approve_no_prompts(tmp_path: Path):
    """Test that -y / auto_approve never prompts for manual review."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# API\n\n::: my_pkg.Client\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: Test\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["migrate", str(tmp_path), "--apply", "-y", "--no-validate"],
    )
    assert result.exit_code == 0
    assert "Constructs Requiring Manual Review" not in result.output
    # Original content preserved
    migrated_content = (docs_dir / "index.md").read_text(encoding="utf-8")
    assert "::: my_pkg.Client" in migrated_content
