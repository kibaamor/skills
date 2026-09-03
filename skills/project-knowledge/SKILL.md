---
name: project-knowledge
description: 'Generate or refresh repository-wide knowledge for coding agents. Use for agent onboarding, knowledge synchronization after structural changes, or a CODE-MAP-only refresh.'
---

# Project Knowledge

Create a compact, evidence-backed, repository-local knowledge system that helps an agent navigate from intent to an observable result without duplicating facts it can cheaply inspect. Treat `AGENTS.md` as the map, not the manual.

## Applicability

Use this skill for repository-wide creation or synchronization of agent guidance, domain language, implemented architecture, and source navigation. For a localized edit to one existing knowledge document, edit that document directly. For code review, runtime debugging, or general documentation, use the corresponding workflow instead.

## Inputs And Outputs

Inputs are the repository root, the user's requested scope, existing knowledge documents, and current repository evidence. Outputs are only the knowledge documents justified by the document-selection rules, plus a completion report. The possible documents are `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md`; none is mandatory solely because it appears in this list.

## Workflow

1. Set the scope to the requested repository or workspace root. Read existing `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md` files. If the requested scope does not align with an identifiable domain boundary, report the mismatch and confirm whether to expand or narrow the scope before proceeding. If no manifest, entry point, or behavior-bearing code exists, report insufficient evidence and stop. This step is complete when the scope and existing knowledge set are known.

2. Choose and state one mode:
   - **Create** when the knowledge set is absent or the user requests full regeneration. Discover the repository as described in step 3. Regeneration may restructure generated material, but preserves supported human-authored guidance and intent.
   - **Refresh** when knowledge documents already exist. Start from the requested scope or structural changes, inspect the affected source paths and their existing document entries, and update only documents made stale by that evidence. Expand to full discovery only when a domain boundary was added or removed, or when a repository-level entry point or manifest changed. Treat a linked knowledge document that is missing or unparseable as stale; recreate it only when step 5's value test selects it, and report the result.
   - If conditions overlap, prefer **Create** when the user requests full regeneration; treat existing documents as human-authored input and preserve claims that evidence supports.

   This step is complete when one mode is stated and, in **Refresh**, the affected scope and missing knowledge documents are named.

3. Read [evidence rules](./references/evidence-rules.md) and build a working evidence ledger. Inventory workspace declarations, manifests, build files, deployment definitions, and their declared entry points across the full scope. When no manifest exists, use executable scripts, build files, imports, and tests as entry-point evidence. Then inspect the 1-3 highest-responsibility behavior-bearing modules and 1-3 focused tests per proposed boundary; increase that sample only when evidence conflicts or a completeness claim requires it. Inspect repository-provided ways to start, drive, observe, and validate the system. Use history only when current files cannot explain an important constraint. For every non-obvious claim, record its owner document, exact source path or command result, confidence, and inventory scope (`complete` or `representative`). This step is complete when every proposed non-obvious claim has a ledger entry and absent or conflicting evidence is explicit.

4. Identify the project's knowledge shape:
   - When project-specific language meets the glossary value test, use one root `CONTEXT.md` for one coherent domain language.
   - Use multiple context-local `CONTEXT.md` files plus one root `CONTEXT-MAP.md` only when independently owned areas use distinct models or the same words with different meanings.
   - Split by domain boundary, not by directory count, service count, deployment unit, or technical layer.

   Resolve ambiguity from evidence; ask at most one focused question per unresolved boundary, and only when the answer would materially change a boundary or operating instruction. This step is complete when every identified domain belongs to exactly one context and the need for `CONTEXT-MAP.md` is decided.

5. Read [document contracts](./references/document-contracts.md), then:
   a. Apply its document-selection rules and edit only the justified files at the locations defined there.
   b. Preserve supported human-authored content and local conventions.
   c. Correct human-authored claims about current behavior when stronger evidence contradicts them.
   d. Preserve contradicted rationale or intended ownership only as explicitly labelled intent, alongside the conflict and evidence needed to resolve it; never present it as implemented architecture.
   e. Document stable constraints and rationale, and link to authoritative files instead of copying recoverable snapshots.

   This step is complete when each selected document has evidenced value, each claim has one owner, and affected documents satisfy their contracts.

6. Reconcile the files using the cross-document ownership contract in [document contracts](./references/document-contracts.md). This step is complete when terminology and boundaries agree and no fact has more than one owner document.

7. In **Refresh** mode, reconcile affected `CODE-MAP.md` entries with the current tree: remove dead paths, add affected responsibility-bearing modules and entry points, and update changed test locations or generated-code boundaries. Preserve supported human annotations. Report contradicted annotations as specific unknowns rather than silently replacing them. For a CODE-MAP-only request, leave every other knowledge document byte-for-byte unchanged. This step is complete when every affected path resolves and unrelated documents are unchanged.

8. Audit agent legibility for each documented common or high-risk workflow. Confirm an agent can discover the controlling context, locate the change target, invoke the available action or check, and observe a result using repository-local, versioned artifacts. Document evidenced feedback paths; when a required decision or signal exists only in chat, external documents, or tacit knowledge, report the exact gap and the repository artifact needed to resolve it. Encode recurring guidance in its owner document; report missing enforcement as a guardrail gap. This step is complete when every audited workflow has an observable path or a specific reported gap.

9. Read [adversarial verification](./references/adversarial-verification.md) and apply every relevant check. Compare generated content with the pre-edit knowledge set and remove changes caused only by wording, ordering, or rediscovery of unchanged facts. A repeated run over unchanged evidence must produce no content changes. This step is complete when the reference's verification criterion is met and every remaining diff maps to changed evidence or a contract violation.

10. Perform every applicable [quality check](./references/quality-checks.md), including the bundled deterministic validator. If a referenced instruction file or the bundled validator cannot be read or fails to run, report the missing or failed resource by name and continue with the remaining in-scope checks rather than aborting. In **Refresh** mode, report out-of-scope findings without editing those files. Run repository-declared documentation checks when available; report unavailable checks and their missing prerequisites. This step is complete when all in-scope mechanical checks pass and every remaining contradiction is a specific unknown.

11. Report the mode, files created or updated, key evidence, agent-legibility or guardrail gaps, remaining unknowns, and checks performed. This step is complete when the report accounts for every performed or unavailable check.
