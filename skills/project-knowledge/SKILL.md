---
name: project-knowledge
description: 'Generate or refresh repository knowledge for coding agents: AGENTS.md, domain CONTEXT.md files, optional CONTEXT-MAP.md, ARCHITECTURE.md, and CODE-MAP.md. Use when documenting or onboarding to an entire repository, or synchronizing affected knowledge documents after structural changes, including a CODE-MAP-only refresh. Do not use for isolated prose edits or changing a single glossary term.'
---

# Project Knowledge

Create a compact, evidence-backed, repository-local knowledge system that helps an agent navigate from intent to an observable result without duplicating facts it can cheaply inspect. Treat `AGENTS.md` as the map, not the manual.

## Workflow

1. Set the scope to the requested repository or the workspace root. Read existing `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md` files. If the repository contains no discoverable manifests, entry points, or code, report that insufficient evidence exists and stop.

2. Choose one mode:
   - **Create** when the knowledge set is absent or the user requests full regeneration. Discover the repository as described in step 3. Regeneration may restructure generated material, but preserves human-authored claims. When repository evidence contradicts a human-authored domain claim, keep the human claim, mark it with the conflicting evidence and its source path, and list it under remaining unknowns in the final report.
   - **Refresh** when knowledge documents already exist. Start from the requested scope or structural changes, inspect the affected source paths and their existing document entries, and update only documents made stale by that evidence. Expand to full discovery only when a domain boundary was added or removed, or when a repository-level entry point or manifest changed. If some expected knowledge documents are missing or unparseable, create the missing documents from evidence while refreshing the rest, and report which documents were newly created.
   - If both conditions partially apply (for example, some documents exist but the user requests full regeneration), prefer Create mode and treat existing documents as human-authored input to preserve where evidence supports them.

3. Discover evidence. Read the root manifest and workspace configuration, then every package manifest and executable entry point they declare. Inspect build, test, and deployment configuration, responsibility-bearing modules, and 1-3 tests per identified domain boundary (from existing documents in Refresh mode, or from discovered code structure in Create mode) that call the boundary's public entry points directly and assert on its externally observable behavior. If no such tests exist, report this as an unknown. Also inspect repository-provided ways an agent can start, drive, observe, and validate the system, such as isolated development environments, UI or API drivers, logs, metrics, traces, and focused checks. Use history only when current files cannot explain an important constraint. Maintain a working evidence ledger for every non-obvious claim: proposed owner document, exact source path or command result, confidence (`verified` or `unknown`), and whether the claim is a complete inventory or a representative example. The ledger is working state, not an output document.

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

7. In refresh mode, reconcile `CODE-MAP.md` with the current tree: remove dead paths, add affected responsibility-bearing modules and entry points, and update changed test locations or generated-code boundaries. Preserve human annotations supported by current code. If a human annotation is contradicted by current code in Refresh mode, do not silently delete it; update the affected entry and report the conflict as a specific unknown, mirroring Create mode.

8. Audit agent legibility for each documented common or high-risk workflow. Confirm an agent can discover the controlling context, locate the change target, invoke the available action or check, and observe a result using repository-local, versioned artifacts. Document evidenced feedback paths; when a required decision or signal exists only in chat, external documents, or tacit knowledge, report the exact gap and the repository artifact needed to resolve it. When this run exposes a recurring failure mode, encode a durable rule in its owning document if guidance is sufficient; when enforcement is required, report the missing lint, structural test, or tool as a guardrail gap rather than writing an aspirational rule.

9. Verify facts adversarially before final reconciliation:
   - **Command tracing:** For every command, trace the complete script chain and run the narrowest safe non-destructive invocation when its prerequisites are available. If the chain or prerequisites cannot be verified, record the command as an unknown.
   - **Safe invocation:** Treat an invocation as safe only when it reads state without writing files outside a temporary directory, mutating external systems, making authenticated network calls, or altering the working tree. When in doubt, do not run it and record the claim as an unknown.
   - **Gated claims:** For environment-, branch-, deployment-, security-, and feature-gated claims, enumerate the configured values and inspect every controlling condition rather than inferring production behavior from a label. If any configured value or condition remains uninspected, downgrade the claim to a specific unknown.
   - **Domain definitions:** Confirm cardinality, lifecycle, and ownership from behavior-bearing code or focused tests rather than names or README prose alone. If behavior-bearing evidence is incomplete, downgrade the definition to a representative example or a specific unknown.
   - **Counterexamples:** Search for counterexamples to claims about dependency direction, uniqueness, absence, completeness, or isolation. If the search covers only part of the relevant scope, downgrade the claim to a representative example or a specific unknown.

10. Always perform [quality checks](./references/quality-checks.md). In Refresh mode, checks are diagnostic outside the requested or evidence-affected documents: report those findings without editing out-of-scope files. Additionally run documentation lint, link checking, diagram validation, or documentation builds declared by the repository. If a declared check cannot be executed because of missing tooling or an environment failure, skip it and report it as an unknown with the reason; do not fabricate results or block completion on unavailable tooling. Resolve every in-scope contradiction or report it as a specific unknown.

11. Report the mode, files created or updated, key evidence, agent-legibility or guardrail gaps, remaining unknowns, and checks performed. Use this completion checklist:

- Claims with available evidence are supported, and missing evidence is reported as an unknown.
- Every high-risk claim (commands, tests, deployment, security gates, generated files, and destructive or append-only procedures) has direct evidence in the working ledger and passed its applicable adversarial check.
- Every documented common or high-risk workflow has an agent-accessible path from controlling context to an observable validation result, or a specific reported gap.
- Boundaries and terminology are consistent.
- Completion is blocked by unresolved and unreported contradictions, unsupported high-risk claims, duplicate fact ownership, broken local links, or undocumented agent-legibility gaps; unavailable checks and missing evidence are reportable unknowns, not blockers when stated explicitly.

## Editing Rules

- Keep each fact in one authoritative document and link to it elsewhere.
- Keep generated documents concise enough to scan; disclose detail through links to nearby documentation.
- Prefer repository-local, versioned, agent-readable sources over knowledge that requires access to external conversations or a maintainer's memory.
- Write stable constraints and rationale, not snapshots that are easy to recover from the repository.
- In refresh mode, modify only the specific entries or sentences made stale by new evidence; do not rewrite unaffected sections or replace human-authored guidance merely to conform to a template.
- Ask a focused question only when an unresolved choice would materially change a domain boundary or operating instruction.
