# CI/CD & Hosting Migration Specification

## 1. GitHub Actions Workflows

### Detection Heuristics (`.github/workflows/*.yml`):
- Steps containing `mkdocs build`, `mkdocs gh-deploy`, or `uv run mkdocs`.
- Actions using `actions/deploy-pages@v...` or `peaceiris/actions-gh-pages@v...`.

### Transformation Mapping:
```yaml
# Before (MkDocs)
- name: Build documentation
  run: uv run mkdocs build --strict
- name: Deploy to GitHub Pages
  run: uv run mkdocs gh-deploy --force

# After (Sphinx + MyST)
- name: Build documentation
  run: uv run sphinx-build -W -b html docs docs/_build/html
- name: Deploy to GitHub Pages
  uses: actions/upload-pages-artifact@v3
  with:
    path: docs/_build/html
```

---

## 2. Read the Docs (`.readthedocs.yaml`)

### Detection & Transformation:
```yaml
# Before (MkDocs on Read the Docs)
version: 2
mkdocs:
  configuration: mkdocs.yml

# After (Sphinx on Read the Docs)
version: 2
sphinx:
  configuration: docs/conf.py
  fail_on_warning: true
```
