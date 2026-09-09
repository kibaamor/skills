---
name: project-knowledge-generator
description: "Generate or refresh repository-wide knowledge for coding agents: operating guidance, domain language, architecture, and source navigation. Use for onboarding, structural-change synchronization, full regeneration, or CODE-MAP-only refreshes; not localized edits to one existing document."
---

# Project Knowledge Generator

Create a compact, evidence-backed knowledge system that helps agents find where to work, what to preserve, which source is authoritative, and how to validate a change. Treat `AGENTS.md` as the entry point, not the encyclopedia.

## Rules

- Honor the user's scope, language, format, preservation, and named-document requirements. A requirement is compatible with a document when it is within the user's scope and fits that document's contract. Apply compatible requirements to every affected document. Preserve code, commands, paths, identifiers, product names, and canonical domain terms unless the user explicitly requests translation.
- Treat existing knowledge as human-authored unless a repository marker or generator proves otherwise. Preserve supported guidance and rationale. A current-state claim describes what the repository does now; intent describes a goal, plan, rationale, or ownership claim not established by current implementation. Correct contradicted current-state claims; retain contradicted intent only as labelled unresolved intent.
- Give each durable fact one owner document. Link to that owner or to repository source instead of copying facts that are cheap to inspect. When an affected durable fact is duplicated across selected documents, choose the single most appropriate owner according to the ownership rules, replace the affected copies with links to it, and note the consolidation in the report. In Refresh mode, do not consolidate unrelated duplicates outside the requested or changed evidence.

## Workflow

1. **Scope and mode.** Identify the repository root, extract the user's checkable requirements, and inventory existing root and nested knowledge documents before editing.
   - Use **Create** when the knowledge set is absent or the user requests full regeneration.
   - Use **Refresh** when knowledge documents exist; limit discovery and edits to facts affected by the request or structural changes. A full-regeneration request takes precedence over existing documents.
   - Apply the sufficiency gate before drafting: continue when the repository has at least one manifest, entry point, build or executable script, or behavior-bearing source file; otherwise report insufficient evidence and stop.
   - Handle conflicts after the sufficiency gate: ask one focused question only when an unresolved conflict requires a user choice before any compatible output can be produced. Otherwise proceed, update evidenced non-conflicting facts, and report the conflict as a specific unknown or unresolved intent.

2. **Build evidence.** Read [evidence rules](./references/evidence-rules.md). If this or any other referenced reference document cannot be read, report the missing reference and stop rather than proceeding with assumed rules. Inventory workspace declarations, manifests, build and deployment definitions, and declared entry points across the requested scope. Trace relevant entry points through behavior-bearing code and focused tests. Inspect repository-provided ways to start, drive, observe, and validate the system. In Refresh mode, use Git status and rename-aware diffs when available.

   Keep one working evidence ledger. Record each non-obvious claim as a row with these fields:
   - `claim`
   - `owner_document`
   - `exact_source_or_command_result`
   - `confidence`
   - `inventory_scope`
   - `source_of_truth_classification`
   - `contradictions`
   - `staleness` (Refresh mode only)

   Sample only for descriptive characterization: claims about typical patterns or representative examples. For any completeness, absence, uniqueness, or isolation claim, including claims using `all`, `none`, `only`, or `every`, search the full stated scope. When fewer than 10 files remain in scope, inspect all of them rather than sampling.

3. **Select documents.** Read [document contracts](./references/document-contracts.md) and apply its value tests and ownership rules. Split context glossaries by evidenced domain language, not by directory, service, deployment unit, or technical layer. Create or retain only documents with evidenced value.

4. **Draft or refresh.** Edit only selected, affected documents. Follow their contracts, preserve supported local guidance, and use canonical terminology consistently. Document stable relationships, constraints, source-of-truth locations, and observable feedback paths; report missing evidence or repository-local guardrails instead of guessing.

   In Refresh mode, remove or correct affected stale paths, commands, names, boundaries, tests, and generated-code mappings. Recreate a missing linked document only when its value test still passes. For a CODE-MAP-only request, leave every other knowledge document byte-for-byte unchanged.

5. **Verify.**
   - Treat documented commands, source-of-truth or generated-output classifications, gated behavior, domain cardinality/lifecycle/ownership, and completeness, absence, uniqueness, or isolation claims as high-risk.
   - Apply [adversarial verification](./references/adversarial-verification.md) to those high-risk claims.
   - Perform every applicable [quality check](./references/quality-checks.md).
   - Compare the final diff with the pre-edit knowledge set and remove unrelated wording, ordering, or formatting changes.
   - Confirm that a repeated run over unchanged evidence would produce no content changes.

6. **Report.** In the requested output language, name the mode, changed files, applied requirements, decisive evidence and classifications, stale claims or unresolved intent, remaining unknowns or guardrail gaps, and checks performed or unavailable.
