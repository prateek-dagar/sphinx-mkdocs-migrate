# API Documentation Compatibility Specification

## 1. Systems in Scope
- `mkdocstrings` (Python handler / Griffe)
- `mkautodoc`
- `sphinx.ext.autodoc`
- `sphinx.ext.autosummary`
- `sphinx.ext.napoleon` (Google & NumPy style docstrings)

## 2. Parameter Normalization & Variadic Matching
- When using `autodoc_class_signature = "separated"`, ensure variadic parameters (`*args`, `**kwargs`) in docstrings match constructor signatures without emitting missing-parameter warnings.
