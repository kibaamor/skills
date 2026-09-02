# Quality Checks

Run this checklist after creating or updating project knowledge.

## Evidence

- Every command exists in a manifest, task definition, CI workflow, or maintained project documentation. Trace nested scripts to the final executable and verify that every referenced script exists.
- Every command's executable is supplied by the repository, documented environment, or stated prerequisite; a script name alone does not prove it can run. Run the narrowest safe non-destructive command when prerequisites are available; otherwise report it as unverified with the missing prerequisite.
- Every named component, boundary, runtime interaction, datastore, and external dependency has a current repository source.
- Claims that a test is isolated, focused, unit-level, or runnable are verified from its imports, setup, side effects, and package discovery rules.
- Inferences cite independent supporting evidence appropriate to the claim, such as a manifest plus its entry point or a handler plus its focused test; otherwise label the inference as an unknown and state the missing evidence.
- Environment and feature-gated claims use configured environment values and the exact controlling conditions as evidence. Security behavior is not inferred from environment names.
- CI and deployment claims account for branch, variable, scheduled, and fan-out conditions in the workflow. A documented example is labelled representative unless all branches were inspected.
- Domain definitions involving cardinality, lifecycle, duration, status, or ownership are supported by behavior-bearing code or focused tests. Names and prose documentation alone are insufficient.
- Claims about dependency direction, uniqueness, absence, or isolation include a repository-wide counterexample search within the stated scope.
- Pre-existing claims contradicted by current evidence are corrected. When the evidence cannot determine the replacement, report the contradiction as a specific unknown; preserve only claims that current evidence supports or does not disprove.
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

- `AGENTS.md` is a short entry-point map with explicit pointers to deeper owners; it does not become a monolithic repository encyclopedia.
- Setup and validation commands appear under clearly named `AGENTS.md` headings or direct links from them; finding a runnable command does not require searching another prose document.
- Instructions name their scope, trigger, action, and observable completion condition.
- Each documented common or high-risk workflow gives an agent a discoverable chain from controlling context, to the responsible code, to an available action or check, to an observable result. Missing links are reported as agent-legibility gaps rather than filled with guesses.
- When the repository provides isolated runtimes, UI or API drivers, logs, metrics, traces, or other validation harnesses, the knowledge set routes agents to them without copying machine-readable configuration.
- Required knowledge that exists only in external conversations, unlinked documents, or maintainer memory is reported with the repository-local artifact needed to make it available to agents.
- Each `CODE-MAP.md` component entry links to a source root or executable entry point that owns the named responsibility.
- Each mapped responsibility links to the file or directory that directly controls it and, when available, co-locates its nearest focused test.
- Unknowns name the unresolved claim, the evidence inspected, and the evidence or maintainer decision needed to resolve it.
- `AGENTS.md` states a completion contract, and every named check is runnable under the executable-availability rule above or explicitly reports its prerequisite.

## Maintainability

- Machine-readable facts are linked instead of copied unless lookup would be unusually expensive.
- Each fact has one owner; other documents link to it.
- Every `CODE-MAP.md` path exists, stale paths are removed, and newly introduced responsibility-bearing areas are represented.
- Every instruction or claim is tied to named repository evidence or a specific reported unknown; stale migration notes and unexplained acronyms are absent.
- Recurring failure modes discovered during generation are captured once as durable guidance when guidance is sufficient; failures that require enforcement are reported as concrete lint, structural-test, or tooling gaps.
- Copied counts, versions, port lists, environment lists, and file inventories are omitted when they can be recovered cheaply from machine-readable sources. When a snapshot is necessary, label its scope and evidence date.
- Existing human-authored constraints and rationale are preserved unless repository evidence disproves them.

## Mechanical Checks

- Every relative Markdown link resolves with exact path casing.
- Headings are unique within each document and form a hierarchy without skipped levels.
- Mermaid blocks declare a diagram type and have balanced syntax; run the repository's diagram checker when configured.
- Repository documentation lint, formatting, and link checks pass when configured and available; otherwise report the unavailable executable or environment prerequisite.

## Final Reconciliation

Read the generated files once in this order: root `AGENTS.md`; root `CONTEXT.md`, or `CONTEXT-MAP.md` followed by every discovered context glossary; root `ARCHITECTURE.md` followed by every authoritative package-level architecture document; `CODE-MAP.md`; then each nested `AGENTS.md` against the subtree it governs. Confirm that terminology, context names, component names, boundary descriptions, and source paths agree across all files. For each paragraph, identify one owner document; replace repeated facts in other documents with links. Recheck every high-risk claim against the working evidence ledger, then apply the completion blockers in `SKILL.md` step 10.
