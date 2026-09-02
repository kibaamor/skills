---
name: project-knowledge
description: 'Generate or refresh repository knowledge for coding agents: AGENTS.md, domain CONTEXT.md files, optional CONTEXT-MAP.md, ARCHITECTURE.md, and CODE-MAP.md. Use when documenting or onboarding to an entire repository, or synchronizing affected knowledge documents after structural changes, including a CODE-MAP-only refresh. Do not use for isolated prose edits or changing a single glossary term.'
---

# Project Knowledge

Create a compact, evidence-backed knowledge system that helps an agent act correctly without duplicating facts it can cheaply inspect.

## Workflow

1. Set the scope to the requested repository or the workspace root. Read existing `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md` files. If the repository contains no discoverable manifests, entry points, or code, report that insufficient evidence exists and stop.

2. Choose one mode:
   - **Create** when the knowledge set is absent or the user requests full regeneration. Discover the repository as described in step 3. Regeneration may restructure generated material, but preserves human-authored claims unless repository evidence disproves them; report unresolved conflicts instead of deleting or guessing.
   - **Refresh** when knowledge documents already exist. Start from the requested scope or structural changes, inspect the affected source paths and their existing document entries, and update only documents made stale by that evidence. Expand to full discovery only when a domain boundary was added or removed, or when a repository-level entry point or manifest changed. If some expected knowledge documents are missing or unparseable, create the missing documents from evidence while refreshing the rest, and report which documents were newly created.
   - If both conditions partially apply (for example, some documents exist but the user requests full regeneration), prefer Create mode and treat existing documents as human-authored input to preserve where evidence supports them.

3. Discover evidence. Read the root manifest and workspace configuration, then every package manifest and executable entry point they declare. Inspect build, test, and deployment configuration, responsibility-bearing modules, and 1-3 representative tests per identified domain boundary (from existing documents in Refresh mode, or from discovered code structure in Create mode), prioritizing tests that exercise the boundary's public interface. Use history only when current files cannot explain an important constraint. Keep source paths for claims and mark unresolved facts as unknown.

4. Identify the project's knowledge shape:
   - Use one root `CONTEXT.md` when the project has one coherent domain language.
   - Use multiple context-local `CONTEXT.md` files plus one root `CONTEXT-MAP.md` when independently owned areas use distinct models or the same words with different meanings.
   - Split by domain boundary, not by directory count, service count, deployment unit, or technical layer.

5. Read [document contracts](./references/document-contracts.md), then edit the required files directly at the locations defined there. Preserve supported human-authored content and local conventions. Prefer links to authoritative files over copied facts that will drift.

6. Reconcile the documents as one system:
   - `AGENTS.md` tells an agent how to work and where deeper knowledge lives.
   - `CONTEXT.md` defines domain language without implementation details.
   - `CONTEXT-MAP.md` indexes domain boundaries and their relationships.
   - `ARCHITECTURE.md` explains the implementation structure, runtime interactions, constraints, and important design rationale.
   - `CODE-MAP.md` maps responsibilities and change targets to concrete source paths, entry points, and tests.

7. In refresh mode, reconcile `CODE-MAP.md` with the current tree: remove dead paths, add affected responsibility-bearing modules and entry points, and update changed test locations or generated-code boundaries. Preserve human annotations supported by current code.

8. Always perform [quality checks](./references/quality-checks.md). Additionally run documentation lint, link checking, diagram validation, or documentation builds declared by the repository. If a declared check cannot be executed because of missing tooling or an environment failure, skip it and report it as an unknown with the reason; do not fabricate results or block completion on unavailable tooling. Resolve every contradiction or report it as a specific unknown.

9. Report the mode, files created or updated, key evidence, remaining unknowns, and checks performed. Use this completion checklist:
   - Claims with available evidence are supported, and missing evidence is reported as an unknown.
   - Boundaries and terminology are consistent.
   - Completion is blocked only by unresolved contradictions or broken local links; unavailable checks and missing evidence are reportable unknowns, not blockers.

## Editing Rules

- Keep each fact in one authoritative document and link to it elsewhere.
- Keep generated documents concise enough to scan; disclose detail through links to nearby documentation.
- Write stable constraints and rationale, not snapshots that are easy to recover from the repository.
- In refresh mode, modify only the specific entries or sentences made stale by new evidence; do not rewrite unaffected sections or replace human-authored guidance merely to conform to a template.
- Ask a focused question only when an unresolved choice would materially change a domain boundary or operating instruction.
