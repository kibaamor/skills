# Quality Checks

Run this checklist after creating or updating project knowledge.

## Evidence

- Every command exists in a manifest, task definition, CI workflow, or maintained project documentation.
- Every command's executable is supplied by the repository, documented environment, or stated prerequisite; a script name alone does not prove it can run.
- Every named component, boundary, runtime interaction, datastore, and external dependency has a current repository source.
- Claims that a test is isolated, focused, unit-level, or runnable are verified from its imports, setup, side effects, and package discovery rules.
- Inferences are either verified by a second source or explicitly labelled as unknown.
- Current behavior and intended future architecture are clearly distinguished.

## Document Boundaries

- `AGENTS.md` contains operational instructions rather than a repository encyclopedia.
- Each `CONTEXT.md` contains domain definitions only.
- `CONTEXT-MAP.md` exists only for multiple genuine bounded contexts and links to every context glossary.
- `ARCHITECTURE.md` owns implementation structure and runtime relationships.
- `CODE-MAP.md` owns source navigation and does not duplicate architecture prose.
- Architecture exception lists are exhaustive for their stated scope or explicitly labelled as representative examples.
- ADR-worthy rationale is linked rather than duplicated.

## Agent Utility

- An agent can find the correct setup and validation commands quickly.
- Instructions name their scope, trigger, action, and observable completion condition.
- Component descriptions link to useful entry points or source roots.
- Each mapped responsibility leads to a useful edit or reading target and, when available, its nearest focused test.
- Unknowns are visible and specific enough for a maintainer to resolve.

## Maintainability

- Machine-readable facts are linked instead of copied unless lookup would be unusually expensive.
- Each fact has one owner; other documents link to it.
- Every `CODE-MAP.md` path exists, stale paths are removed, and newly introduced responsibility-bearing areas are represented.
- No generic advice, stale migration notes, unexplained acronyms, or speculative claims remain.
- Existing human-authored constraints and rationale are preserved unless repository evidence disproves them.

## Mechanical Checks

- Every relative Markdown link resolves with exact path casing.
- Headings are unique and form a sensible hierarchy.
- Mermaid blocks declare a diagram type and have balanced syntax; run the repository's diagram checker when configured.
- Repository documentation lint, formatting, and link checks pass when configured.

## Final Reconciliation

Read the generated files once in this order: `AGENTS.md`, `CONTEXT-MAP.md` or `CONTEXT.md`, `ARCHITECTURE.md`, then `CODE-MAP.md`. Confirm that terminology, context names, component names, boundary descriptions, and source paths agree across all files. Completion requires every contradiction to be resolved or explicitly reported as an unknown.
