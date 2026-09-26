# Documentation Construct & Migration Specification Matrix

| Construct | Origin Layer | MkDocs Input | Target (MyST / Sphinx) | Strategy | Notes & Transformation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Heading H1** | CommonMark / GFM | `# Title` | MyST `# Title` / Docutils H1 | `Preserve` | Validate header anchor ID references |
| **Heading H2..H6** | CommonMark / GFM | `## Subtitle` | MyST `## Subtitle` | `Preserve` | Preserve hierarchy for `toctree` generation |
| **Document Link** | CommonMark / MkDocs | `[text](doc.md)` | MyST `[text](doc.md)` / `:doc:` | `Transform` | Normalize relative file targets to Sphinx docnames |
| **External Link** | CommonMark | `[text](https://...)` | `[text](https://...)` | `Preserve` | Pass-through |
| **Anchor / HTML ID** | HTML / Markdown | `<a id="foo">` / `{#foo}` | MyST `(foo)=` / HTML block | `Transform` | Map to MyST target headers for cross-referencing |
| **Image** | CommonMark | `![alt](img.png)` | `![alt](img.png)` / `{image}` | `Preserve` | Verify static assets directory configuration |
| **Code Block** | CommonMark / GFM | ```` ```python ```` | ```` ```python ```` / `{code-block}` | `Preserve` | Verify language highlightinglexer support |
| **Line Highlighting**| PymdownX (SuperFences)| ```` ```python hl_lines="1 3" ```` | ```` ```python --- :emphasize-lines: 1,3 ```` | `Transform` | Map PymdownX options to MyST code-block options |
| **Admonition (Note)**| Python-Markdown | `!!! note` | MyST ````{note}```` | `Transform` | Map syntax; support optional titles |
| **Admonition (Warn)**| Python-Markdown | `!!! warning` | MyST ````{warning}```` | `Transform` | Direct directive mapping |
| **Admonition (Tip)** | Python-Markdown | `!!! tip` | MyST ````{tip}```` | `Transform` | Direct directive mapping |
| **Details / Fold**   | PymdownX (Details) | `??? note "Title"` | MyST ````{dropdown} Title```` / `{details}` | `Transform` | Requires `sphinx-design` or compatibility extension |
| **Content Tabs**     | PymdownX (Tabbed) | `=== "Python"` | ````{tab-set} \n ````{tab-item} Python```` | `Transform` | Requires `sphinx-design` tab directives |
| **Definition List**  | Python-Markdown | `Term \n : Definition` | MyST Definition List | `Preserve` | Enable `deflist` extension in `myst_enable_extensions` |
| **Markdown Table**   | GFM | `\| Col1 \| Col2 \|` | MyST Markdown Table | `Preserve` | Native support |
| **API Module**       | `mkdocstrings` | `::: my_module` | Sphinx `.. automodule:: my_module` | `Transform` | Convert to `autodoc` directive or autosummary |
| **API Class**        | `mkdocstrings` | `::: my_module.MyClass` | Sphinx `.. autoclass:: MyClass` | `Transform` | Handle constructor signature separation |
| **API Function**     | `mkdocstrings` | `::: my_module.func` | Sphinx `.. autofunction:: func` | `Transform` | Map handler options |
| **Variadic Parameters**| Google Docstrings | `*args: ...` / `**kwargs: ...` | Napoleon `:param *args:` | `Transform/Fix` | Fix `sphinx-immaterial` normalization mismatch |
| **Navigation (`nav`)**| MkDocs Core | `nav:` tree in `mkdocs.yml` | `toctree` directives | `Transform` | Generate `index.md` / `toctree` hierarchy |
| **Theme Specifics**  | Material for MkDocs| Badges, icons, buttons | `sphinx-immaterial` / `sphinx-design` | `Theme-Adapter`| Map to theme directives or compatibility extension |
