# Quality Checks

Run every applicable check after creating or refreshing project knowledge.

## Contract

- Every affected document satisfies the user's compatible requirements; unresolved conflicts are specific and visible.
- Every retained document passes its [selection test](./document-contracts.md#selection), and every fact follows the [scope partition](./document-contracts.md#scope-partition) and [ownership table](./document-contracts.md#ownership).
- Human-authored guidance and rationale required by the preservation rules remain intact. Contradicted current-state claims are corrected; contradicted intent remains only as labelled unresolved intent.
- In Functional module scope, the knowledge root follows the placement rules and every supporting document passes its value test for that module. Unless the request is CODE-MAP-only, `MODULE.md` exists after the sufficiency gate passes.
- When module knowledge sets exist, one authoritative project-level module map contains exactly one resolving conditional pointer per module and no module-local detail beyond that pointer. A user exclusion or CODE-MAP-only request may leave a missing entry unchanged when the report names the gap.

## Evidence

- Every non-obvious current-state claim meets the confidence standard in [evidence rules](./evidence-rules.md#confidence).
- Source-of-truth, generated, derived, duplicated, and documentation-only facts are classified correctly.
- Equal-authority conflicts, weak evidence, missing prerequisites, and absent repository signals are reported as specific unknowns rather than published as facts.
- Completeness and absence claims cover their full stated scope; other inventories are labelled representative.
- Functional module identity, reachability, observable outcomes, included anchors, boundary edges, and exclusions are verified or reported as specific unknowns. For each documented lifecycle or mutation flow, the knowledge names an actual trigger or caller and observable outcome; a containing-file link alone does not establish reachability. Unrelated sibling evidence does not satisfy the module sufficiency gate.
- Current-state claims seeded by discovery-only material independently meet the confidence standard from durable controlling evidence; transferred rationale and constraints remain distinguishable from implemented behavior and external state.
- Every runtime-boundary claim ends in one evidenced outcome: verified behavior or compatibility, including any accepted or queued delivery semantics; a verified defect with downstream consequences; or a specific unknown. Reachability, completion, acknowledgement, and external-effect ordering are traced; hand-built fixtures and mocked call order are not treated as production proof.

## Utility and Consistency

- Terminology, context names, component names, boundaries, paths, and source classifications agree across the complete selected knowledge set.
- Entry-point and summary documents do not state stronger compatibility, ordering, or success guarantees than their detailed owners; defects and unknowns remain visible wherever the affected behavior would otherwise appear operational.
- Repository and module documents satisfy the [scope partition](./document-contracts.md#scope-partition) and link to shared or external owners.
- Outside CODE-MAP-only work, search all inventoried managed project-level knowledge for module actors, responsibilities, triggers, outcomes, internal flows, local terms, constraints, rationale, commands, checks, and source or test paths. Reconcile each affected passage under the scope partition. Do not remove a project-level copy before every claim required by the preservation rules has a valid final owner; preserve and report any ownership blocker as incomplete partitioning. In CODE-MAP-only work, report copies outside the selected `CODE-MAP.md` as gaps.
- Every documented common or high-risk workflow leads from context and responsible code to an available action or check and an observable result. Report a precise agent-legibility or guardrail gap when the chain is incomplete.
- Each retained paragraph helps an agent decide where to work, what to preserve, which source is authoritative, or how to validate. Remove the rest.
- In full Functional module work, each map entry reaches `MODULE.md`, or the report names the user-imposed discovery gap. The diff changes only the selected or required module knowledge sets, the authoritative module map, every inventoried project-level scope-partition violation reconciled under that partition, and a root `CONTEXT-MAP.md` update required by a selected module glossary. Against the pre-edit bytes, inspect every hunk this run introduced in a pre-existing project-level document: keep only the map update, required context-map update, and removal or replacement of module-local knowledge.
- In Repository work, every published module-local fact is owned by a module knowledge set that passed the sufficiency gate. A preserved ownership blocker remains unchanged and is reported as incomplete partitioning. Project-level `ARCHITECTURE.md` and `CODE-MAP.md` otherwise retain only repository-wide or shared knowledge and route module discovery through the authoritative module map.
- In module CODE-MAP-only work, `CODE-MAP.md` is the only changed knowledge document; pre-existing missing or stale `MODULE.md`, module-map entry, boundary claim, or project-level duplicate remains unchanged and is reported as a gap.
- In Refresh mode, the diff contains only affected facts or user-requested presentation changes. A CODE-MAP-only refresh changes no other repository or module knowledge document.

## Mechanical Checks

Use repository-configured documentation checks when they exist. If no configured checker covers these items, manually check every created or modified knowledge document and every context or package document it links, then report the checked scope:

- Every local file link resolves with exact path case from the document location.
- Every same-file or cross-file heading anchor points to an existing heading.
- Heading levels progress without skipping required hierarchy for the document's structure.
- Every Mermaid block has a declared diagram type and no obvious unbalanced brackets, quotes, or code fences.
- Every documented command names an existing script, binary, Make target, task, or repository file that controls it.
- For each final-reference prohibition, no created or modified knowledge document contains the artifact's exact path, a local link to it, its unambiguous basename, or an instruction to consult it; removing the artifact leaves every knowledge link resolvable.

Report missing executables or environment prerequisites. Use the repository's Mermaid checker when configured because the manual Mermaid check is only a syntax screen, not a full parser.

## Final Reconciliation

Read the complete selected knowledge set once. Confirm that every request requirement is accounted for, every module map link resolves to `MODULE.md`, no selected project-level document repeats its module-local owner content unless the unchanged passage is a reported ownership blocker, every remaining diff maps to changed evidence or a contract violation, every unknown states what would resolve it, and a second run over unchanged evidence would be byte-for-byte stable.
