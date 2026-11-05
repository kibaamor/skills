# Candidate Verification

## Task

Independently determine whether each supplied Finding is real and whether each Recommendation is materially worthwhile for this project. Treat all candidates as unproven. This is focused verification, not a new broad review.

## Review target and binding requirements

{{REVIEW_TARGET_AND_REQUIREMENTS}}

## Baseline change package

{{BASELINE_CHANGE_PACKAGE}}

Use the baseline diff to distinguish changed behavior from pre-existing behavior. Inspect current code and baseline code where needed. If the baseline does not establish introduction status, leave attribution unknown; do not let attribution determine whether the underlying issue is real.

## Candidate Findings — unproven claims

{{CANDIDATE_FINDINGS}}

## Candidate Recommendations — unproven proposals

{{CANDIDATE_RECOMMENDATIONS}}

## Relevant technical context and task-specific checks

{{RELEVANT_TECHNICAL_CONTEXT}}

Only use checks that apply to the candidate under examination. Do not re-read unrelated project guidance or conduct unrelated repository exploration.

## Existing validation evidence

{{EXISTING_VALIDATION_EVIDENCE}}

Treat reported tests as claims until their commands, outputs, assertions, and exercised paths are available. A passing test proves only what it actually asserted and exercised; a test name or summary is not broad correctness evidence.

## How to verify Findings

For each Finding candidate:

1. Locate the cited implementation and inspect the smallest necessary surrounding path.
2. Reconstruct the relevant caller preconditions, control/data flow, state transitions, ownership/lifecycle, concurrency, protocol behavior, and error handling.
3. Determine whether the trigger is reachable and whether the implementation violates the stated requirement/invariant.
4. Actively seek counter-evidence: input validation, guards, synchronization, cleanup, cancellation, retry/idempotency behavior, transaction boundaries, caller constraints, and authoritative contracts.
5. Decide whether the claimed impact actually follows and is material.
6. Run a focused test or temporary reproducer when it can materially confirm or falsify the claim. Inspect the command for side effects first and follow the validation boundary below.

Verdicts:

- `confirmed`: implementation evidence and a reachable scenario establish the claimed issue and material impact;
- `rejected`: concrete counter-evidence falsifies the claim; lack of reproduction alone is insufficient;
- `uncertain`: evidence is incomplete or conflicting;
- `not_verifiable`: necessary code, contract, baseline, or environment evidence is unavailable.

## How to assess Recommendations

For each Recommendation candidate:

1. Check that the description of the current approach matches the implementation.
2. Determine whether the proposed alternative is feasible and compatible with project requirements.
3. Compare the likely net effect on correctness, simplicity, maintainability, performance, reliability, extensibility, and testability as relevant.
4. Account for effort, new complexity, migration/compatibility risk, and operational cost.

Verdicts:

- `worthwhile`: material net benefit and good project fit;
- `optional`: reasonable but modest/discretionary improvement;
- `not_better`: no meaningful net benefit or worse after trade-offs;
- `context_dependent`: missing/variable constraints determine the choice;
- `not_verifiable`: necessary evidence is unavailable.

Recommendations are not defects and receive no severity. Pattern or aesthetic preference is not a benefit.

## Executable validation boundary

You MAY run focused tests, builds, analyzers, and temporary reproduction scripts when they materially improve confidence. Inspect commands and invoked scripts for side effects first. Use temporary/disposable output locations. Do not modify reviewed source, permanent tests, project configuration, dependency files, generated project assets, or VCS state. Do not install dependencies, deploy, or mutate shared/production services. Follow the detailed policy supplied here:

{{VALIDATION_BOUNDARY}}

Record exact commands, exit status, assertions/scope, observed output, artifacts, and side effects. If a check cannot safely run, state why and choose the appropriate uncertainty verdict when material.

## Output format

Return exactly one raw JSON object, without Markdown fences or surrounding prose:

```json
{
  "schema_version": "2.1",
  "review_status": "complete",
  "summary": "Concise verification summary",
  "finding_assessments": [
    {
      "candidate_id": "C-F-001",
      "verdict": "confirmed",
      "rationale": "Why the evidence confirms or falsifies the candidate",
      "evidence": ["path/file.ext:10-14 — exact evidence"]
    }
  ],
  "recommendation_assessments": [
    {
      "candidate_id": "C-R-001",
      "verdict": "worthwhile",
      "rationale": "Net benefit and trade-off assessment",
      "evidence": ["path/file.ext:20-25 — relevant evidence"]
    }
  ],
  "checks": [
    {
      "check_id": "V-01",
      "kind": "test",
      "purpose": "Verify C-F-001",
      "command": "go test ./path/to/package -run TestCase",
      "status": "passed",
      "exit_code": 0,
      "scope": "What the test actually exercised",
      "output_summary": "Observed result",
      "artifacts": [],
      "side_effects": "Temporary output only; project and VCS unchanged"
    }
  ],
  "checks_not_run": [],
  "limitations": []
}
```

Return exactly one assessment for each supplied candidate, preserving each candidate ID verbatim. Do not calculate missing/unknown ID inventories; the Controller performs that deterministic check. `checks` contains only commands actually executed. `checks_not_run` explains relevant omitted checks. Do not add unrelated discoveries. Do not include chain-of-thought.
