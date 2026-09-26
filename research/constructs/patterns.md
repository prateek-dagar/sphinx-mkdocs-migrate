# Construct Scanner & Syntax Signatures Catalog

This catalog defines the exact regular expressions and token-matching heuristics used by the **Analyzer Module** to discover and classify constructs across all `.md` source files.

---

## 1. Admonitions & Callouts (Python-Markdown / Material)

### Regex Pattern:
```regex
^(?P<indent>[ ]{0,3})!{3}[ ]+(?P<type>note|warning|tip|info|important|caution|danger|bug|example|quote|abstract|check|question|fail|success)(?:[ ]+"(?P<title>[^"]*)")?
```

- **Target MyST Directive**: ```` ```{<type>} <title> ```` or ````{note}````
- **Classifier State**: `TRANSFORM`
- **Fallback**: Unknown admonition types map to ````{admonition} <type>````

---

## 2. Collapsible Details (PymdownX Details)

### Regex Pattern:
```regex
^(?P<indent>[ ]{0,3})\?{3}(?:\+|-)?[ ]+(?P<type>note|warning|tip|info|details)?[ ]+"(?P<title>[^"]+)"
```

- **Target MyST Directive**: ````{dropdown} <title>```` (via `sphinx-design`)
- **Classifier State**: `TRANSFORM`
- **Feature Flag**: `???+` (initially open) maps to `:open:` option in `dropdown`.

---

## 3. Content Tabs (PymdownX Tabbed)

### Regex Pattern:
```regex
^(?P<indent>[ ]{0,3})={3}[ ]+"(?P<tab_title>[^"]+)"
```

- **Target MyST Directive**: ````{tab-set} \n ````{tab-item} <tab_title>````
- **Classifier State**: `TRANSFORM`

---

## 4. API Directives (mkdocstrings)

### Regex Pattern:
```regex
^:::[ ]+(?P<symbol>[a-zA-Z0-9_\.]+)
```

- **Target Sphinx Directive**:
  - Module: `.. automodule:: <symbol>`
  - Class: `.. autoclass:: <symbol>`
  - Function: `.. autofunction:: <symbol>`
- **Classifier State**: `TRANSFORM`

---

## 5. Relative Markdown Document Links

### Regex Pattern:
```regex
\[(?P<text>[^\]]+)\]\((?P<path>[^)]+\.md)(?:#(?P<anchor>[a-zA-Z0-9_\-]+))?\)
```

- **Target MyST Construct**: Normalize relative document paths to Sphinx document target references (`[text](path/to/doc.md)` or `{doc}` / `{ref}`).
- **Classifier State**: `TRANSFORM`

---

## 6. Snippet / File Includes (PymdownX Snippets)

### Regex Pattern:
```regex
^--8<--[ ]+"(?P<filepath>[^"]+)"
```

- **Target MyST Directive**: ````{include} <filepath>````
- **Classifier State**: `TRANSFORM`

---

## 7. Custom Material Icons & Badges

### Regex Pattern:
```regex
:(?P<icon_set>material|fontawesome|octicons)-[a-zA-Z0-9_\-]+:
```

- **Target**: `sphinx-immaterial` icon substitutions or `sphinx-design` badges.
- **Classifier State**: `TRANSFORM` (with theme adapter) / `MANUAL` (generic).
