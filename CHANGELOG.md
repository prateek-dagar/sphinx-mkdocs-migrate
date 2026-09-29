# Changelog

All notable changes to this project are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Interactive pre-flight confirmation prompt before applying migrations to disk (`-y` / `--yes` to auto-approve).
- Interactive manual review resolution during migration (`-i` / `--interactive`) with options to keep original content, comment out blocks (`<!-- MANUAL_REVIEW: ... -->`), or provide custom MyST replacement text.
- Automatic detection of missing Sphinx dependencies in the active environment with prompt to install them (`--install-deps`).
- Automatic detection of obsolete MkDocs packages in the active environment with prompt to uninstall them (`--uninstall-mkdocs`).

### Fixed


## [0.0.1.dev0] - 2026-09-29

### Added

- First development snapshot of the MkDocs-to-Sphinx migration engine.
- Initial pre-release packaging, CI, documentation, and contributor tooling.
