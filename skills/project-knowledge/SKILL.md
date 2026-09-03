---
name: project-knowledge
description: 'Generate or refresh repository-wide knowledge for coding agents. Use for agent onboarding, knowledge synchronization after structural changes, or a CODE-MAP-only refresh.'
---

# Project Knowledge

Create a compact, evidence-backed, repository-local knowledge system that helps an agent navigate from intent to an observable result without duplicating facts it can cheaply inspect. Treat `AGENTS.md` as the map, not the manual.

## Applicability

Use this skill for repository-wide creation or synchronization of agent guidance, domain language, implemented architecture, and source navigation. For a localized edit to one existing knowledge document, edit that document directly. For code review, runtime debugging, or general documentation, use the corresponding workflow instead.

## Inputs And Outputs

Inputs are the repository root, the user's request, existing knowledge documents, and current repository evidence. Treat explicit user requirements for scope, output language, audience, detail, format, preservation, and named documents as a request contract that applies throughout the workflow. Outputs are only the knowledge documents justified by the document-selection rules, plus a completion report. The possible documents are `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md`; none is mandatory solely because it appears in this list.

## Workflow

1. Establish the scope and request contract in this order:
   a. Set the scope to the requested repository or workspace root. This sub-step is complete when the root and its included paths are explicit.
   b. Extract the request contract, including every explicit requirement that changes selection or presentation. This sub-step is complete when each requirement is checkable.
   c. Read existing `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md` files only after extracting the request contract. This sub-step is complete when the existing knowledge set is known.
   d. When an output language is requested, use it consistently for headings and explanatory prose in every created or updated knowledge document and in the completion report; preserve code, commands, paths, identifiers, product names, and canonical domain terms exactly unless the user explicitly requests their translation. Use the repository documentation's established language only when the user did not choose one. If a user requests translation of a canonical term that has no established target-language form, keep the original term and add a parenthetical gloss on first use. This sub-step is complete when the applicable language rule and preserved terms are recorded in the request contract.
   e. If a requirement conflicts with repository evidence, document contracts, or another requirement, report the exact conflict and ask one focused question only when the answer materially changes the output. This sub-step is complete when every material conflict is resolved or explicitly blocked on one answer.
   f. Check that the requested scope aligns with an identifiable domain boundary. If it does not, report the mismatch and confirm whether to expand or narrow the scope before proceeding. This sub-step is complete when the scope matches a domain boundary or the user confirms the intended adjustment.
   g. Check for a manifest, entry point, or behavior-bearing code. If none exists, report insufficient evidence and stop. This sub-step is complete when at least one of these evidence sources is identified or the workflow has stopped.

2. Choose and state one mode:
   - **Create** when the knowledge set is absent or the user requests full regeneration. Discover the repository as described in step 3. Regeneration may restructure generated material, but preserves supported human-authored guidance and intent.
   - **Refresh** when knowledge documents already exist. Start from the requested scope or structural changes, inspect the affected source paths and their existing document entries, and update only documents made stale by that evidence. Expand to full discovery only when a domain boundary was added or removed, or when a repository-level entry point or manifest changed. Treat a linked knowledge document that is missing or unparseable as stale; recreate it only when step 5's value test selects it, and report the result.
   - If conditions overlap, prefer **Create** when the user requests full regeneration; treat existing documents as human-authored input and preserve claims that evidence supports.

   This step is complete when one mode is stated and, in **Refresh**, the affected scope and missing knowledge documents are named.

3. Read [evidence rules](./references/evidence-rules.md) and build a working evidence ledger. Inventory workspace declarations, manifests, build files, deployment definitions, and their declared entry points across the full scope. When no manifest exists, use executable scripts, build files, imports, and tests as entry-point evidence. Then inspect the 1-3 behavior-bearing modules with the most inbound import or call references from declared entry points, ranked by reference count with ties broken by path in alphabetical order, and 1-3 focused tests per proposed boundary; increase that sample only when evidence conflicts or a completeness claim requires it. Inspect repository-provided ways to start, drive, observe, and validate the system. Use history only when current files cannot explain an important constraint. For every non-obvious claim, record its owner document, exact source path or command result, confidence, and inventory scope (`complete` or `representative`). This step is complete when every proposed non-obvious claim has a ledger entry and absent or conflicting evidence is explicit.

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
   f. Apply every compatible request-contract requirement to every created or updated document. In Refresh mode, a request that explicitly changes language, format, or another presentation property makes each selected document that violates it affected; preserve the supported meaning of human-authored content while bringing that affected content into compliance.

   This step is complete when each selected document has evidenced value, each claim has one owner, and affected documents satisfy both their document contracts and the request contract.

6. Reconcile the files using the cross-document ownership contract in [document contracts](./references/document-contracts.md). This step is complete when terminology and boundaries agree and no fact has more than one owner document.

7. In **Refresh** mode, reconcile affected `CODE-MAP.md` entries with the current tree: remove dead paths, add affected responsibility-bearing modules and entry points, and update changed test locations or generated-code boundaries. Preserve supported human annotations. Report contradicted annotations as specific unknowns rather than silently replacing them. For a CODE-MAP-only request, leave every other knowledge document byte-for-byte unchanged. This step is complete when every affected path resolves and unrelated documents are unchanged.

8. Audit agent legibility for each documented common or high-risk workflow. Confirm an agent can discover the controlling context, locate the change target, invoke the available action or check, and observe a result using repository-local, versioned artifacts. Document evidenced feedback paths; when a required decision or signal exists only in chat, external documents, or tacit knowledge, report the exact gap and the repository artifact needed to resolve it. Encode recurring guidance in its owner document; report missing enforcement as a guardrail gap. This step is complete when every audited workflow has an observable path or a specific reported gap.

9. Read [adversarial verification](./references/adversarial-verification.md) and apply every relevant check. Compare generated content with the pre-edit knowledge set and remove changes caused only by wording, ordering, or rediscovery of unchanged facts. A repeated run over unchanged evidence must produce no content changes. This step is complete when the reference's verification criterion is met and every remaining diff maps to changed evidence or a contract violation.

10. Perform every applicable [quality check](./references/quality-checks.md), including the bundled deterministic validator. Check every created or updated document against every request-contract requirement rather than inferring whole-set compliance from one sample. If a referenced instruction file or the bundled validator cannot be read or fails to run, report the missing or failed resource by name and continue with the remaining in-scope checks rather than aborting. In **Refresh** mode, report out-of-scope findings without editing those files. Run repository-declared documentation checks when available; report unavailable checks and their missing prerequisites. This step is complete when all in-scope mechanical checks and request-contract checks pass and every remaining contradiction is a specific unknown.

11. In the requested output language, report the mode, files created or updated, request-contract requirements applied, key evidence, agent-legibility or guardrail gaps, remaining unknowns, and checks performed. This step is complete when the report accounts for every request requirement and every performed or unavailable check.
