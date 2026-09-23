# Evidence Rules

Use evidence that directly controls or demonstrates the claim. This order is a default, not a substitute for matching evidence to the question:

1. Behavior-bearing source code.
2. Build, dependency, workspace, deployment, or runtime configuration.
3. Focused tests and safe command results.
4. Maintained repository documentation.
5. Names and directory structure.

Names and prose are leads, not proof of runtime behavior. Tests prove only the behavior and environment they exercise. Configuration proves declared behavior only when its entry point and controlling conditions agree.

## Source Classification

- **Source of truth**: directly controls behavior or structure, such as source code, schemas, manifests, build files, deployment definitions, or test harnesses.
- **Generated**: produced from a source of truth. Document where to edit and where output appears.
- **Derived**: reflects another artifact, such as a cache, report, lockfile, index, or diagram. Use it as a lead unless repository policy makes it authoritative for the claim.
- **Duplicated**: repeats a fact controlled elsewhere. Verify it against the controlling source.
- **Documentation-only intent**: records rationale, policy, ownership, or target architecture not established by current implementation. Label it as intent.
- **Discovery-only**: a user-designated temporary or deletion-bound artifact, or one prohibited as a final reference. Decompose it into claims under the rules below; do not promote it wholesale.

## Discovery-only Inputs

- Use behavior, path, version, command, and configuration claims from discovery-only inputs only as search leads. Publish them only when durable controlling source, configuration, focused tests, or command results independently meet the confidence standard.
- Transfer durable rationale, accepted tradeoffs or risks, non-goals, and maintenance constraints to their contract owner only when they apply to evidenced implemented behavior and have no contradiction. State them as rationale or constraints, not as proof of behavior. Treat repository-unverifiable external state as a prerequisite or unknown, and speculative future work as intent.
- On output surfaces covered by the user's prohibition, do not name, cite, link, or direct readers to the discovery-only artifact. The durable owner must remain understandable and navigable without it.

## Confidence

- **Verified**: direct evidence appropriate to the claim was inspected.
- **Strong inference**: at least two independent sources support the claim, direct proof is unavailable, and the stated search scope contains no counterexample.
- **Weak inference**: one indirect source suggests the claim. Use it to guide inspection, not as published project knowledge.
- **Unknown**: evidence is absent, contradictory, unsafe to obtain, or outside the repository. Report the claim, inspected evidence, and what would resolve it.

Publish current-state claims only when verified or strongly inferred. State the support for strong inferences that affect architecture, workflow, or boundaries.

## Conflicts and Scope

- For current behavior, prefer the source that controls that behavior over prose or derived artifacts.
- When equal-authority sources disagree, report an unknown instead of choosing one.
- Preserve contradicted human-authored rationale or ownership only as unresolved intent, with the implementation conflict.
- Label an inventory `complete` only after searching its full stated scope; otherwise label it `representative`.
- In Refresh mode, use Git history and diffs to locate changes, then verify claims against current source and configuration.
