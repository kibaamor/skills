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
