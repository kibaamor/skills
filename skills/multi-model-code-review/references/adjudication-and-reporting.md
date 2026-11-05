# Adjudication and Reporting

## Finding threshold

A Finding must identify a concrete code location, implementation evidence, a reachable trigger or affected scenario, the violated requirement/invariant or specific material engineering weakness, and a credible impact. A style preference, pattern preference, speculative scale concern, or missing test without a concrete risk is not a Finding.

- `confirmed`: evidence establishes the claim, trigger, and material impact.
- `rejected`: implementation behavior or counter-evidence falsifies the claim. Lack of reproduction alone is not rejection.
- `uncertain`: evidence is incomplete or conflicting.
- `not_verifiable`: necessary code, contract, environment, or runtime evidence is unavailable.

Severity is impact under realistic conditions, not confidence:

- `critical`: catastrophic or broadly exploitable impact (e.g. RCE, severe auth bypass, widespread irreversible corruption).
- `high`: major capability failure, serious security compromise, significant corruption, or reachable crash/deadlock/protocol break.
- `medium`: material but bounded failure, subset of states/users, or practical workaround.
- `low`: real actionable defect with limited impact or rare but plausible trigger.

Introduction status is separate: `introduced`, `pre_existing`, or `unknown`. Do not attribute a historical issue to the change without baseline evidence. A pre-existing defect can still be confirmed when it violates a requirement relevant to the changed behavior.

## Recommendation threshold

A Recommendation is a non-defect improvement opportunity. It must contain current approach, concrete alternative, expected benefits, trade-offs/costs, and project fit. Verdicts:

- `worthwhile`: material net benefit and good fit;
- `optional`: useful but modest/discretionary;
- `not_better`: no meaningful net benefit or worse after costs;
- `context_dependent`: depends on missing/variable constraints;
- `not_verifiable`: necessary evidence unavailable.

Never assign bug severity to Recommendations.

## Consolidation

Merge only same-root-cause findings or materially identical proposals. Preserve all source reviewer IDs, local IDs, locations, and distinct evidence. Do not drop a unique candidate merely because other reviewers missed it. Never use majority vote as proof.

## Verification coverage

Controller maintains expected candidate ID sets and checks actual results mechanically. For findings:

`missing = expected_finding_ids - returned_finding_ids`

`unexpected = returned_finding_ids - expected_finding_ids`

Also detect duplicates. Repeat for recommendations. Any gap is a verification coverage failure; the Reviewer does not calculate these sets.

## Report

Include target/baseline and scope; reviewers and model routes actually dispatched; prompt-template validation status; raw-output/schema/semantic validation status; confirmed Findings (severity, location, evidence, trigger, impact, verification); Recommendations (current approach, alternative, benefits, costs, fit); rejected/uncertain/unverifiable candidates; exact tests/builds/commands and their scope/results; checks not run and reasons; workspace/VCS side-effect assessment; and remaining limitations.

State `COMPLETE`, `PARTIAL`, or `BLOCKED` truthfully. COMPLETE means the review workflow met its stated scope and validation gates; it does not mean defect-free code or merge approval.
