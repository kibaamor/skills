# Quality Checks

Run this checklist after creating or updating project knowledge.

## Evidence

- Every command exists in a manifest, task definition, CI workflow, or maintained project documentation.
- Every command's executable is supplied by the repository, documented environment, or stated prerequisite; a script name alone does not prove it can run.
- Every named component, boundary, runtime interaction, datastore, and external dependency has a current repository source.
- Claims that a test is isolated, focused, unit-level, or runnable are verified from its imports, setup, side effects, and package discovery rules.
- Inferences cite independent supporting evidence appropriate to the claim, such as a manifest plus its entry point or a handler plus its focused test; otherwise label the inference as an unknown and state the missing evidence.
- Current behavior and intended future architecture use explicit labels such as `Current` and `Target`; migration actions appear in `AGENTS.md` only while the migration is active.
- Any list presented as complete states its scope; incomplete discovery lists are explicitly labelled as representative.

## Document Boundaries

- Every `AGENTS.md` paragraph changes agent behavior through a repository-specific command, trigger, action, constraint, prerequisite, or completion condition; component inventories and explanatory architecture prose are absent.
- Each `CONTEXT.md` contains domain definitions only.
- `CONTEXT-MAP.md` exists only for multiple genuine bounded contexts; every discovered context glossary is linked from it, and every linked glossary exists.
- `ARCHITECTURE.md` owns implementation structure and runtime relationships.
- Root `ARCHITECTURE.md` links every established package-level architecture document that remains authoritative; unlinked or obsolete package-level architecture documents are reported for maintainer review.
- `CODE-MAP.md` owns source navigation and does not duplicate architecture prose.
- Architectural invariants and their rationale live in `ARCHITECTURE.md`; `AGENTS.md` links to them and contains only the enforcing command or action and its completion condition.
- For generated, vendored, migration, configuration, and deployment areas, `CODE-MAP.md` owns locations, `AGENTS.md` owns handling procedures, and `ARCHITECTURE.md` includes only design consequences.
- ADR-worthy rationale is linked rather than duplicated.

## Agent Utility

- Setup and validation commands appear under clearly named `AGENTS.md` headings or direct links from them; finding a runnable command does not require searching another prose document.
- Instructions name their scope, trigger, action, and observable completion condition.
- Each `CODE-MAP.md` component entry links to a source root or executable entry point that owns the named responsibility.
- Each mapped responsibility links to the file or directory that directly controls it and, when available, co-locates its nearest focused test.
- Unknowns name the unresolved claim, the evidence inspected, and the evidence or maintainer decision needed to resolve it.
- `AGENTS.md` states a completion contract, and every named check is runnable under the executable-availability rule above or explicitly reports its prerequisite.

## Maintainability

- Machine-readable facts are linked instead of copied unless lookup would be unusually expensive.
- Each fact has one owner; other documents link to it.
- Every `CODE-MAP.md` path exists, stale paths are removed, and newly introduced responsibility-bearing areas are represented.
- Every instruction or claim is tied to named repository evidence or a specific reported unknown; stale migration notes and unexplained acronyms are absent.
- Existing human-authored constraints and rationale are preserved unless repository evidence disproves them.

## Mechanical Checks

- Every relative Markdown link resolves with exact path casing.
- Headings are unique within each document and form a hierarchy without skipped levels.
- Mermaid blocks declare a diagram type and have balanced syntax; run the repository's diagram checker when configured.
- Repository documentation lint, formatting, and link checks pass when configured and available; otherwise report the unavailable executable or environment prerequisite.

## Final Reconciliation

Read the generated files once in this order: root `AGENTS.md`; root `CONTEXT.md`, or `CONTEXT-MAP.md` followed by every discovered context glossary; root `ARCHITECTURE.md` followed by every authoritative package-level architecture document; `CODE-MAP.md`; then each nested `AGENTS.md` against the subtree it governs. Confirm that terminology, context names, component names, boundary descriptions, and source paths agree across all files. Completion requires every contradiction to be resolved or explicitly reported as an unknown.
