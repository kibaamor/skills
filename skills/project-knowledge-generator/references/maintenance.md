# Maintenance workflow

Read this guide when refreshing an existing knowledge base after repository changes or repairing confirmed content drift. Default to a scoped update; perform a full refresh only when requested or when broad structural change invalidates the available scope. When a change requires a new knowledge area, also read [the content model](content-model.md).

## Establish the change scope

1. Identify the requested revision range, branch, working-tree change, release, incident, or affected area. If the user supplied a base revision, use it. Otherwise inspect staged and unstaged changes and, when an upstream exists, its merge base with `HEAD`. If no reliable baseline exists, scan the selected scope and report that limitation rather than inventing one.
2. Confirm the knowledge root contains top-level `README.md`, `CONTEXT.md`, and `ARCHITECTURE.md`, with direct links from `README.md` to both canonical pages. If not, stop without editing and report that the Maintain precondition is not satisfied. Otherwise read those files and the focused pages directly associated with the change scope.
3. Inspect Git diffs when available, including staged and unstaged changes when the working tree is in scope. Include untracked files only when relevant to the user's request.
4. Translate file changes into functionality changes: determine whether they add, remove, rename, deprecate, move, gate, or alter an actor-visible capability, trigger, precondition, permission, input, result, side effect, or failure behavior. Treat product docs, registrations, and tests as leads until confirmed against implementation and contracts.
5. Map changed paths through each page's `source_paths`, then expand for the functionality view, public contracts, consumers, shared configuration, and dependency-direction changes.
6. For deleted or renamed files, search capability names and aliases, indexes, Markdown links, path references, and task routes for the former names.

Path overlap identifies a review candidate, not a stale fact. Confirm the page's claims semantically before changing it.

## Change-impact routing

| Repository change | Knowledge to inspect |
|---|---|
| New capability or new public, operator, library, job, or integration entrypoint | `CONTEXT.md` functionality view, task routes, owning area, implementation anchors, contracts, invariants, and tests |
| Capability actor, trigger, prerequisite, permission, flag, result, side effect, or error semantics | Capability entry, main flow, consumers, diagnostics, and verification paths |
| Capability rename, deprecation, replacement, removal, or product entrypoint move | Current name/status, search aliases still accepted or useful, index routes, current consumers, and old anchors still referenced by the project |
| Runtime entrypoint, route, handler, command, or package boundary | `ARCHITECTURE.md`, relevant area pages, task routes |
| API, event, schema, serialization, or public type | Contract explanations, producers/consumers, evidenced product-compatibility guarantees, and data-transition rules |
| State machine, permission, transaction, retry, or ordering behavior | Domain flow, invariants, failures, and focused tests |
| Shared dependency or cross-package call direction | `ARCHITECTURE.md` dependencies, affected areas, build/deploy assumptions |
| Configuration default, feature flag, build file, or CI workflow | Development, configuration, deployment, and verification guidance |
| Logging, metric, trace, alert, or recovery behavior | Diagnostics, runbooks, and failure signals |
| File deletion or rename | Frontmatter paths, local links, index routes, and symbol references |
| Durable new domain or component boundary | Decide whether a new focused page improves task routing |
| Important accepted tradeoff | Add or supersede an ADR; do not rewrite decision history |

## Update rules

- Edit the smallest complete set of affected pages. Do not rewrite the whole knowledge base for stylistic consistency.
- When functionality changes, update the `CONTEXT.md` capability entry, its index/task route, and affected flow, contract, and test guidance as one coherent patch.
- When runtime composition, component boundaries, dependency direction, stores, external systems, or representative flows change, update `ARCHITECTURE.md` and its detailed links in the same patch.
- Do not leave a removed capability described as current. Preserve an old name only when current product behavior still accepts it or it remains useful for source search, and label its status with evidence.
- For a pure refactor, update implementation anchors only when navigation changed; do not rewrite capability behavior when its observable semantics are unchanged.
- Keep capability granularity centered on stable goals and observable results rather than creating one feature per handler, endpoint, screen, or helper.
- Preserve human rationale, annotations, and the existing information architecture unless evidence requires a change.
- Describe the new current state. Put historical explanation in an ADR or link to version history rather than narrating the diff in every page.
- Add a page only for stable, reusable knowledge with a distinct reading trigger. Update the index whenever a new page changes a task route.
- Regenerate deterministic material only inside clearly replaceable generated files or regions. Never let regeneration overwrite curated intent or invariants.
- If code behavior contradicts an accepted decision, record both sides and flag review; do not reconcile the conflict by assumption.
- When evidence is insufficient, keep the prior supported statement or mark the exact item unverified. Do not fill gaps with plausible architecture.
- Advance `verified_commit` only after reviewing every claim on the page against that revision. A mechanical validator must never update it.
- If no semantic knowledge changed, make no cosmetic update merely to refresh dates or commit fields.
- Confirm that repeating the same maintenance operation over unchanged evidence would produce no content changes.

## Candidate-staleness checks

The helper can compare `source_paths` with repository changes:

```bash
python3 <skill-directory>/scripts/project_knowledge.py validate \
  --root <repository> \
  --knowledge-dir <knowledge-directory> \
  --since <revision> \
  --require-yaml
```

Without `--since`, the validator may use a page's `verified_commit`. `STALE_CANDIDATE` means supporting paths changed; it does not prove that prose is obsolete. Review indirect consumers even when their paths do not overlap.

For CI, opt into stricter exit behavior deliberately with `--fail-on-warning` or `--fail-on-stale`. First establish that the repository's existing docs and metadata satisfy the current knowledge model; do not introduce a blocking gate that the project cannot currently meet.

## Full refresh triggers

Consider a full audit after a major directory or architecture restructuring, contract-version change, framework replacement, repository split/merge, major interaction-surface change, broad capability addition/removal/rename, or long period without maintained evidence. A full refresh still preserves confirmed content and existing organization where useful.

Finish by reporting the revision or working-tree scope examined, knowledge files updated, stale candidates reviewed but unchanged, checks run, and unresolved contradictions or missing evidence.
