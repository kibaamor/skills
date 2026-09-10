# Quality Checks

Run every applicable check after creating or refreshing project knowledge.

## Contract

- Every affected document satisfies the user's compatible requirements; unresolved conflicts are specific and visible.
- Every retained document passes its [selection test](./document-contracts.md#selection), and every fact follows the [ownership table](./document-contracts.md#ownership).
- Supported human-authored guidance and rationale remain intact unless current controlling evidence contradicts them.

## Evidence

- Every non-obvious current-state claim meets the confidence standard in [evidence rules](./evidence-rules.md#confidence).
- Source-of-truth, generated, derived, duplicated, and documentation-only facts are classified correctly.
- Equal-authority conflicts, weak evidence, missing prerequisites, and absent repository signals are reported as specific unknowns rather than published as facts.
- Completeness and absence claims cover their full stated scope; other inventories are labelled representative.

## Utility and Consistency

- Terminology, context names, component names, boundaries, paths, and source classifications agree across the complete selected knowledge set.
- Every documented common or high-risk workflow leads from context and responsible code to an available action or check and an observable result. Report a precise agent-legibility or guardrail gap when the chain is incomplete.
- Each retained paragraph helps an agent decide where to work, what to preserve, which source is authoritative, or how to validate. Remove the rest.
- In Refresh mode, the diff contains only affected facts or user-requested presentation changes. A CODE-MAP-only refresh changes no other knowledge document.

## Mechanical Checks

Use repository-configured documentation checks when they exist. If no configured checker covers these items, manually check every created or modified knowledge document and every context or package document it links, then report the checked scope:

- Every local file link resolves with exact path case from the document location.
- Every same-file or cross-file heading anchor points to an existing heading.
- Heading levels progress without skipping required hierarchy for the document's structure.
- Every Mermaid block has a declared diagram type and no obvious unbalanced brackets, quotes, or code fences.
- Every documented command names an existing script, binary, Make target, task, or repository file that controls it.

Report missing executables or environment prerequisites. Use the repository's Mermaid checker when configured because the manual Mermaid check is only a syntax screen, not a full parser.

## Final Reconciliation

Read the complete selected knowledge set once. Confirm that every request requirement is accounted for, every remaining diff maps to changed evidence or a contract violation, every unknown states what would resolve it, and a second run over unchanged evidence would be byte-for-byte stable.
