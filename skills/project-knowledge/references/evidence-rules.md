# Evidence Rules

Match evidence to the claim. Use this default order, moving lower only when higher-ranked evidence cannot answer the question:

1. Behavior-bearing source code.
2. Build, dependency, and workspace configuration.
3. Focused tests and safe command results.
4. Deployment and runtime configuration.
5. Maintained repository documentation.
6. Names and directory structure.

Names and prose are leads, not proof of runtime behavior. A test proves only the behavior and environment it exercises. Configuration proves declared topology or intent only when the corresponding entry point or controlling condition agrees.

## Confidence

- **Verified**: direct evidence appropriate to the claim was inspected. Record the exact source path or command result.
- **Strong inference**: at least two independent sources support the claim, no counterexample was found in the stated search scope, and direct proof is unavailable. Label the inference in the ledger and avoid stronger wording in documents.
- **Weak inference**: one indirect source or naming suggests the claim. Do not publish it as project knowledge; report it only when it identifies useful missing evidence.
- **Unknown**: evidence is absent, contradictory, unsafe to execute, or outside the repository. State the claim, inspected evidence, and what would resolve it.

Published current-state claims must be verified or strong inferences. Keep weak inferences and unknowns in the completion report, not in definitive architecture or operating instructions.

## Conflicts

- Current behavior, paths, commands, dependencies, and deployment conditions follow current controlling code or configuration over prose.
- Human-authored rationale, policy, or intended ownership may describe intent that code cannot prove. Preserve it only when supported; when contradicted, label it as unresolved intent and report the implementation conflict.
- When two sources of equal authority disagree, downgrade the claim to unknown rather than choosing the more convenient source.
- A complete or absent claim requires a full search of its stated scope. Otherwise label the inventory representative.
