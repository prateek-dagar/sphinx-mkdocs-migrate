# Version Boundary & Compatibility Matrix

## 1. Source Ecosystem (MkDocs)

| Component | Target Version Range | Breaking / Distinct Behavior Across Versions |
| :--- | :--- | :--- |
| **MkDocs** | `>= 1.4, < 2.0` | 1.5+ introduced new plugin events & strict validation; 1.6+ updated draft docs support |
| **MkDocs Material** | `>= 8.0, < 10.0` | Syntax evolution for tabs (`content.tabs`), new grid cards, and navigation enhancements |
| **mkdocstrings** | `>= 0.20, < 1.0` | Python handler (`mkdocstrings-python`) split into standalone package; Griffe parser adoption |
| **Pymdown Extensions**| `>= 9.0, < 11.0` | SuperFences, Details, and Tabbed block syntax variations |

## 2. Target Ecosystem (Sphinx)

| Component | Target Version Range | Supported Features / Notes |
| :--- | :--- | :--- |
| **Sphinx** | `>= 7.0, < 9.0` | Modern autodoc enhancements, Python 3.10+ type union rendering |
| **MyST-Parser** | `>= 2.0, < 5.0` | CommonMark + GFM support, directive extensions (`deflist`, `colon_fence`, `attrs_inline`) |
| **sphinx-immaterial** | `>= 0.11` | MkDocs Material look-and-feel for Sphinx; separated signature table rendering |
| **sphinx-design** | `>= 0.5` | Native drop-in for responsive grids, tab-sets, dropdowns, badges, and cards |
