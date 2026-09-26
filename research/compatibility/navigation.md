# Navigation Compatibility Specification

## 1. MkDocs `nav` vs Sphinx `toctree`

### Information Flow:
- **MkDocs**: Declarative YAML list in `mkdocs.yml` defining labels and relative paths.
- **Sphinx**: Document-tree directive (`.. toctree::` or ````{toctree}````) placed in parent documents (`index.md`).

### Mapping Rules:
1. **Flat Navigation**: Single root `toctree` in `docs/index.md`.
2. **Nested Sections**: Sub-index files (`section/index.md`) containing local `toctree` directives.
3. **Explicit Titles**: `Title: path.md` translates to `Title <path.md>` in the `toctree` body.
