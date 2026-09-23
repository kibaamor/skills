---
name: project-knowledge-generator
description: "Create or refresh evidence-backed coding-agent knowledge docs such as AGENTS.md, ARCHITECTURE.md, CODE-MAP.md, CONTEXT.md, or a functional module knowledge base. Use for full regeneration, stale-doc refreshes, and CODE-MAP-only updates. Do not use for explain-only walkthroughs, code review, implementation work, or copy edits and translations that require no repository evidence."
---

# Project Knowledge Generator

Create a compact, evidence-backed knowledge system that helps agents find where to work, what to preserve, which source is authoritative, and how to validate a change. Treat `AGENTS.md` as the discovery entry point, not the encyclopedia.

## Rules

- Honor the user's scope, language, format, preservation, and named-document requirements. A requirement is compatible with a document when it is within the user's scope and fits that document's contract. Apply compatible requirements to every affected document.
- Preserve code, commands, paths, identifiers, product names, and canonical domain terms unless the user explicitly requests translation.
- Treat existing knowledge as human-authored unless explicit provenance proves otherwise: generated frontmatter or a banner naming a generator, repository configuration or scripts declaring the output path, or a committed provenance file. Preserve supported guidance and rationale.
- Distinguish current state from intent. A current-state claim describes what the repository does now; intent describes a goal, plan, rationale, or ownership claim not established by current implementation. Correct a contradicted current-state claim only when the requested scope and document contract select that claim. Retain contradicted intent only as labelled unresolved intent.
- Respect selection scope. Selecting a managed project-level document for a module-map update or duplicate consolidation selects only the affected map and duplicate passages; report unrelated stale claims instead of editing them.
- Give each durable fact one owner document. Apply the scope partition in [document contracts](./references/document-contracts.md#scope-partition): functional-module knowledge belongs to its module knowledge set, while managed project-level knowledge represents that module only through the authoritative module map. Link to the owner or to repository source instead of copying facts that are cheap to inspect. In every non-CODE-MAP-only run, reconcile every managed project-level module fact found by the required inventory under that partition; report completed consolidations and ownership blockers. In Refresh mode, leave unrelated duplicates that do not violate this partition outside the requested or changed evidence.

## Workflow

1. **Scope and mode.** Identify the repository root, choose **Repository** or **Functional module** scope, extract the user's checkable requirements, and inventory existing knowledge before editing. Read [module knowledge](./references/module-knowledge.md) for Functional module scope and whenever Repository inventory finds an existing module knowledge set or a candidate module-local fact. For Functional module scope, identify the module boundary seed before choosing documents or paths; prove the boundary during evidence building.
   - Inventory is complete only after searching the selected scope and its knowledge owners for `AGENTS.md`, `CLAUDE.md`, `MODULE.md`, `CONTEXT*.md`, `ARCHITECTURE.md`, `CODE-MAP.md`, ADR directories, and repository-local agent, rule, or instruction docs. Follow repository configuration, scripts, and local links from discovered knowledge entry points to inventory the custom indexes, roots, and owners covered by the [managed project knowledge](./references/document-contracts.md#scope-partition) definition. Identify existing module knowledge roots and the authoritative module map. Classify each candidate as selected, linked owner, unrelated, or stale before drafting.
   - Use **Create** when the selected repository or module knowledge set is absent, or the user requests full regeneration. Repository knowledge does not make a new module knowledge set a Refresh.
   - Use **Refresh** when knowledge documents exist; limit discovery and edits to facts affected by the request or structural changes. A full-regeneration request takes precedence over existing documents.
   - Apply the sufficiency gate before drafting. Repository scope requires at least one manifest, entry point, build or executable script, or behavior-bearing source file. Functional module scope requires an evidenced trigger or caller, behavior-bearing implementation, and observable outcome for that module; evidence from an unrelated sibling module does not satisfy the gate.
   - Handle conflicts after the sufficiency gate: ask one focused question only when an unresolved conflict requires a user choice before any compatible output can be produced. Otherwise proceed, update evidenced non-conflicting facts, and report the conflict as a specific unknown or unresolved intent.

2. **Build evidence.** Read [evidence rules](./references/evidence-rules.md) and [document contracts](./references/document-contracts.md). If a reference required by the selected branch cannot be read, report the missing reference and stop rather than proceeding with assumed rules. Inventory workspace declarations, manifests, build and deployment definitions, and declared entry points across the requested scope. Trace relevant entry points through behavior-bearing code and focused tests. Inspect repository-provided ways to start, drive, observe, and validate the system. For each selected functional module, follow [module knowledge](./references/module-knowledge.md) for boundary and ownership evidence.

   Treat any artifact the user marks as temporary, deletion-bound, or forbidden as a final reference as [discovery-only](./references/evidence-rules.md#discovery-only-inputs). Apply its claims individually; never promote the artifact as a whole into current project knowledge.

   In Refresh mode, identify the evidence delta before editing and report the baseline used:
   - If the user supplied a base ref, use it.
   - Otherwise use Git metadata only when it belongs to the selected repository root or requested fixture scope. Inspect `git status --short`, `git diff --name-status -M`, and `git diff --cached --name-status -M` there. For a functional module, map changed paths to its evidenced entry points, implementation, tests, and boundary edges; do not filter only by one directory.
   - If `@{upstream}` exists for that same root, compute `git merge-base HEAD '@{upstream}'` and inspect `git diff --name-status -M <base>...HEAD`.
   - If the selected scope is not a Git worktree, or only a parent repository has unrelated metadata, do not infer a delta from the parent repository. Scan the full selected scope and report that no reliable baseline existed.

   Keep one working evidence ledger. Record each user requirement, high-risk claim, non-obvious current-state claim, completeness or absence claim, stale claim, and contradiction as a row with these fields:
   - `claim`
   - `owner_document`
   - `exact_source_or_command_result`
   - `confidence`
   - `inventory_scope`
   - `source_of_truth_classification`
   - `contradictions`
   - `staleness` (Refresh mode only)

   Scale the ledger to the selected scope and claim risk. Evidence build is complete when every required ledger claim has a row, every high-risk current-state claim is verified, strongly inferred, or marked unknown, and every completeness or absence claim records a full-scope search. For runtime-boundary, lifecycle, mutation, migration, reconciliation, or repair claims, keep enough ledger detail to apply [adversarial verification](./references/adversarial-verification.md) without re-reading the whole repository. Ordinary path links, headings, and formatting claims do not need ledger rows; verify them during mechanical checks.

   For Functional module scope, ledger rows must establish the canonical module identity, included behavior anchors, boundary edges, and excluded or shared owners.

   Sample only for descriptive characterization: claims about typical patterns or representative examples. For any completeness, absence, uniqueness, or isolation claim, including claims using `all`, `none`, `only`, or `every`, search the full stated scope. When fewer than 10 files remain in scope, inspect all of them rather than sampling.

3. **Select documents.** Apply the document contract value tests and scope partition. For CODE-MAP-only work, select only the requested `CODE-MAP.md` and report ownership violations elsewhere as gaps. Otherwise select the module knowledge set for every module-local fact that will be published or moved, every managed project-level document containing a scope-partition violation, and the authoritative module map for its routing entries. Follow [module knowledge](./references/module-knowledge.md) for Create, Refresh, and CODE-MAP-only document selection. Create other documents only when their value tests pass. Split context glossaries by evidenced domain language, not by directory, service, deployment unit, technical layer, or the mere existence of a functional module.

4. **Draft or refresh.** Edit only selected, affected documents. Follow their contracts, preserve supported local guidance, and use canonical terminology consistently. In CODE-MAP-only work, edit only the requested `CODE-MAP.md` and report out-of-scope ownership gaps. Otherwise reconcile every inventoried module-local fact under the scope partition and leave one routing entry per completed module knowledge set in the authoritative module map. Document stable relationships, constraints, source-of-truth locations, and observable feedback paths; report missing evidence or repository-local guardrails instead of guessing.

   In Refresh mode, remove or correct affected stale paths, commands, names, boundaries, tests, and generated-code mappings. Recreate a missing linked document only when its value test still passes. For Functional module Refresh, full regeneration, or CODE-MAP-only work, follow [module knowledge](./references/module-knowledge.md) for location stability and isolation.

5. **Verify.**
   - Treat documented commands, source-of-truth or generated-output classifications, gated behavior, functional-module identity and boundary, domain cardinality/lifecycle/ownership, runtime-boundary guarantees, and completeness, absence, uniqueness, or isolation claims as high-risk.
   - Apply [adversarial verification](./references/adversarial-verification.md) to those high-risk claims.
   - Perform every applicable [quality check](./references/quality-checks.md).
   - Reconcile every high-risk ledger row against its final owner passage so the published claim is no stronger than the verified evidence.
   - Outside CODE-MAP-only work, verify the final knowledge set and any ownership blocker against the scope partition, and confirm that each map entry resolves to its module owner. In CODE-MAP-only work, confirm that the selected `CODE-MAP.md` follows its scope contract and report violations in unselected knowledge documents as gaps.
   - Compare the final diff with the pre-edit knowledge set and remove unrelated wording, ordering, or formatting changes.
   - Confirm that a repeated run over unchanged evidence would produce no content changes.

6. **Report.** In the requested output language, use this compact report shape and omit empty sections: `Scope`, `Mode`, `Changed Files`, `Requirements Applied`, `Decisive Evidence`, `Consolidations`, `Ownership Blockers`, `Stale or Unresolved Claims`, `Unknowns or Guardrail Gaps`, `Checks`.
