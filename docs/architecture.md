# Architecture Overview

`sphinx-mkdocs-migrate` is designed as a pipeline of decoupled, testable subsystems:

```text
                  Source Repository (mkdocs.yml + Markdown)
                                     │
                                     ▼
                           [ProjectAnalyzer]
                                     │
                        ┌────────────┴────────────┐
                        ▼                         ▼
             [MarkdownParser (IR)]       [FeaturePolicyCatalog]
                        │                         │
                        ▼                         ▼
             [MigrationRuleEngine] ─────► [MigrationPlanner]
                                                  │
                                                  ▼
                                         <MigrationPlan>
                                                  │
                        ┌─────────────────────────┴─────────────────────────┐
                        ▼                                                   ▼
             [TransformationEngine]                              [TransformationValidator]
                        │                                                   │
                        ▼                                                   ▼
          Transformed Markdown & conf.py                        Isolated Sandbox Sphinx Build
```

## Subsystem Responsibilities

1. **`ProjectAnalyzer`**: Discovers project layout, parses `mkdocs.yml`, inspects navigation trees, dependencies, and CI workflows.
2. **`MarkdownParser` & IR**: Generates structured intermediate representation (IR) with exact source line mappings and fence isolation.
3. **`MigrationRuleEngine`**: Evaluates declarative migration rules against IR nodes, yielding categorized actions (`TRANSFORM`, `PRESERVE`, `MANUAL`, `UNSUPPORTED`).
4. **`FeaturePolicyCatalog` & `PolicyEngine`**: Translates detected theme features, extensions, and plugins into deterministic Sphinx requirements, MyST syntax flags, and `conf.py` settings.
5. **`MigrationPlanner`**: Synthesizes findings, rules, and policy outcomes into a reproducible, read-only `MigrationPlan` with stable hashes.
6. **`TransformationEngine`**: Applies planned transformations atomically, preserving untouched Markdown byte-for-byte.
7. **`TransformationValidator`**: Runs structural AST validations and builds documentation in an isolated temporary sandbox.
