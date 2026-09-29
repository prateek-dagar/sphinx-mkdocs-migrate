---
name: Bug report
about: Report unexpected behaviour or migration errors to help us improve
title: ''
labels: bug
assignees: ''
---
<!--
Hi there! Thank you for wanting to make sphinx-mkdocs-migrate better 😉.

Please perform a quick search first, in order to check if your problem has already been reported:
https://github.com/prateek-dagar/sphinx-mkdocs-migrate/issues
-->

## Describe the Bug
A clear and concise description of what went wrong during analysis or migration.

## Error Details & Traceback
If an exception or error occurred, please paste the full terminal output or traceback here:
```
<paste traceback / log here>
```

## Minimal Reproducible Example
Please include the minimal `mkdocs.yml` snippet or markdown structure that reproduces the issue:
```yaml
# Minimal mkdocs.yml snippet
site_name: Minimal Reproducer
plugins: []
```

Command executed:
```bash
sphinx-migrate plan --mkdocs-config mkdocs.yml
```

## Environment
- **OS**: [e.g. macOS 15.0 / Ubuntu 24.04 / Windows 11]
- **Python version**: [e.g. 3.12.7]
- **sphinx-mkdocs-migrate version**: [run `sphinx-migrate --version`]
