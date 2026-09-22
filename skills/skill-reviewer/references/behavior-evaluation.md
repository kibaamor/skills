# Behavioral evaluation

Use this reference when reviewing output quality, investigating inconsistent
behavior, or verifying that an important revision helps.

## Choose the evidence level

Identity-bound existing outputs, traces, or a retained single-configuration
pilot support `outputs_observed`. Inspect and report that evidence without
creating a comparison campaign. Use the remaining paired workflow only for a
comparative claim or evidence that a revision helps.

## Start with a small real test set

Begin with two or three cases. Each case contains a realistic user prompt, a
human-readable expected outcome, and optional input files. Vary wording and
detail, and include at least one malformed, boundary, or ambiguous case.

Use the target skill's `evals/evals.json` as read-only input when it exists.
Store new or modified definitions and fixtures under the isolated evaluation
workspace, leaving the target unchanged while review findings are formed:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": "descriptive-id",
      "prompt": "A realistic user request with paths and context",
      "expected_output": "Observable characteristics of success",
      "files": ["<input-file-path>"]
    }
  ]
}
```

The root accepts only `skill_name` and `evals`; a case accepts only `id`,
`prompt`, `expected_output`, `files`, and `assertions`. The validator reports
unknown fields so misspellings and incompatible eval dialects are visible.
String names and IDs are compared after trimming surrounding whitespace.

With an external definition, fixture paths are relative to its workspace root;
`--skill-root` names the immutable skill whose name is being checked. Validate
the definition before running:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py validate-evals /path/to/example-skill-workspace/evals/evals.json --skill-root /path/to/example-skill --pretty
```

Observe the first outputs before adding detailed assertions. Add those
assertions to the workspace copy, not the target package. This keeps the
initial test from encoding guesses about how a good solution must look.

## Set the success bar

Turn the pilot outputs into assertions that are objective, observable, and
robust to wording. Use scripts for mechanical facts such as JSON validity or
file dimensions; use an LLM judge for semantic claims.

Before the first paired run, write an immutable `evaluation-plan.json` at the
workspace root. Record a campaign identifier; configuration labels, the fixed
baseline identity, and the revised target's starting identity under the
`candidate` configuration; the execution
environment; case IDs, prompts, inputs, and output contracts; each case's
assertion texts; acceptable quality, time, and token deltas; and a maximum
iteration count. Use three iterations when the user supplies no other limit.
Changing an evaluation input, environment, assertion, or bar starts a new
campaign. The revised target is the measured variable, so record its exact
identity in each iteration instead of rewriting the plan. Here `candidate` is
the comparison configuration name, not a separate skill copy.

The aggregator validates this minimum machine-readable subset and permits
additional frozen fields for prompts, inputs, output contracts, bars, and the
iteration limit:

```json
{
  "schema_version": 1,
  "campaign_id": "review-2026-09-21-a",
  "environment_identity": "client/model/harness identity",
  "candidate": {
    "name": "with_skill",
    "starting_package_identity": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  },
  "baseline": {
    "name": "old_skill",
    "package_identity": "sha256:2222222222222222222222222222222222222222222222222222222222222222"
  },
  "acceptance": {
    "min_candidate_pass_rate": 0.95,
    "min_pass_rate_delta": 0.0,
    "max_time_seconds_delta": 5.0,
    "max_tokens_delta": 10000,
    "max_baseline_only": 0
  },
  "evals": [
    {
      "id": "descriptive-id",
      "directory": "eval-descriptive-id",
      "assertions": ["An objective frozen assertion"]
    }
  ]
}
```

`schema_version` must be the integer `1`. Package identities must use exactly
`sha256:` plus 64 lowercase hexadecimal digits. Configuration names must equal
the aggregate CLI arguments. Eval IDs and directories must each be unique;
directories are single path components beginning with `eval-`; assertions are
non-empty and unique after trimming. The planned directory set must exactly
match the iteration's discovered `eval-*` directories. All other shown strings
must be non-empty.

`acceptance` is a small allowlist. `min_candidate_pass_rate` and
`min_pass_rate_delta` are required numbers in `[0, 1]` and `[-1, 1]`
respectively. `max_time_seconds_delta` and `max_tokens_delta` are optional
non-negative numbers; `max_baseline_only` is an optional non-negative integer.
The latter caps the total `baseline_only` assertion instances across complete
pairs. Unknown acceptance fields are rejected. Bounds are inclusive, with only
one-unit-in-the-last-place tolerance for floating-point boundary arithmetic.
Omitting an optional maximum deliberately leaves that dimension outside the
automated gate, so retain and report its metric separately.

## Bind evidence to the reviewed package

Attach the configuration identity, exact applicable package identity, frozen
campaign identity, and execution-environment identity to each configuration's
retained provenance. If any required identity cannot be established, report
that limitation and do not present the run as regression evidence for another
version.

Obtain package identities from a successful static preflight where
`package_inventory_complete` and `package_digest_complete` are true. Its
`skill-package-manifest-v1` digest covers every ordinary package file except
regenerated cache artifacts (Python bytecode caches, tool cache directories,
OS folder metadata) with path-sensitive SHA-256 framing; per-file and
whole-package budgets are reported
in `facts.limits`. `package_digest_bytes` is the number of ordinary-file content
bytes hashed against `limits.total_digest_bytes`. When the digest is complete,
it equals the sum of package file sizes; it excludes manifest framing and may
be partial after a digest failure. The aggregator validates identity syntax and
consistency but does not read either package to recreate the digest.

Starting preflight is the freeze boundary. Finish every edit first, then keep
that package revision unchanged through its report. Compute the pre-edit
baseline snapshot identity once; for each revised-target iteration, reuse its
one preflight identity for every run. The workflow relies on revision
immutability; it does not monitor the package for later changes.

After freezing `evaluation-plan.json`, compute `plan_identity` as SHA-256 over
its exact UTF-8 bytes. Whitespace and key order therefore affect the identity.
Do not write this identity back into the plan; doing so would make it
self-referential.

Write this `provenance.json` beside each configuration's grading and timing
files:

```json
{
  "schema_version": 1,
  "campaign_id": "review-2026-09-21-a",
  "eval_id": "descriptive-id",
  "configuration": "with_skill",
  "plan_identity": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
  "package_identity": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
  "environment_identity": "client/model/harness identity"
}
```

The schema, plan digest, campaign, eval, configuration, and environment values
must bind to the plan and directory being aggregated. Baseline package identity
must equal the frozen plan value. Candidate package identity may change between
iterations, but it must be identical across every candidate run in one
iteration.

## Use an isolated paired comparison

Every run starts with a clean context and a unique output directory. Give both
sides the identical prompt, inputs, and output contract.

When independent workers are available, launch both sides before inspecting
either result. Otherwise run them sequentially in fresh contexts; do not let the
first output change the second run's prompt or contract.

- For a new skill, compare `with_skill` with `without_skill`.
- For authorized remediation, copy the pre-edit target to an isolated,
  read-only baseline snapshot, then edit the original target in place. Compare
  the frozen revised target with that baseline snapshot.

For `without_skill`, baseline `package_identity` identifies the frozen package
intentionally withheld and may equal the candidate identity. The configuration
record and retained harness trace or load manifest must prove that the package
was not loaded.

Use this layout without overwriting prior iterations:

```text
<skill>-workspace/
├── evaluation-plan.json
├── baseline/                     # read-only pre-edit snapshot
└── iteration-N/
    ├── eval-<case>/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   ├── grading.json
    │   │   ├── provenance.json
    │   │   └── timing.json
    │   └── old_skill/              # or without_skill
    │       ├── outputs/
    │       ├── grading.json
    │       ├── provenance.json
    │       └── timing.json
    ├── feedback.md
    └── benchmark.json
```

Keep non-target evaluation fixtures immutable and do not share mutable output
directories between parallel runs. Capture transcripts when the harness
exposes them. Immediately record timing data as:

```json
{"total_tokens": 84852, "duration_ms": 23332}
```

If isolation, observability, authorization, or budget prevents a fair run,
report that limitation instead of presenting a simulated benchmark.

## Grade results

Grade both sides against the same frozen assertions. Every result needs
concrete evidence:

```json
{
  "assertion_results": [
    {
      "text": "The generated configuration is valid JSON",
      "passed": true,
      "evidence": "Parsed outputs/config.json successfully"
    }
  ],
  "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0}
}
```

Require evidence for PASS; do not give ambiguous output the benefit of the
doubt. Revisit assertions that both configurations always pass, both always
fail, or that cannot be checked from the output.

Use blind comparison for holistic qualities such as organization and usability:
hide which output is the candidate. For subjective artifacts, collect the
verdict and reasons before revealing identities or revising the skill. When a
human reviewer is available, save their specific, actionable feedback or an
explicit no-issue result. Otherwise state explicitly that human review was not
performed; LLM judging is not human assurance.

Use the host's native safe artifact presentation instead of building a viewer
for one campaign. In `feedback.md`, record one entry per eval and review lane
with the eval ID, reviewer kind (`human` or `model`), review status (`performed`
or `not_performed`), and blinding status (`blinded`, `unblinded`, or
`not_applicable`). A performed review also records its preference (`A`, `B`,
`tie`, or `inconclusive`), reasons or an explicit no-issue result, and the A/B
mapping. For a blinded review, write the preference and reasons before appending
the mapping. A review that was not performed records the reason, uses
`not_applicable` for blinding, and omits preference and mapping. Do not claim
blinding when the reviewer could observe configuration identities.

## Aggregate and interpret

After every run has `grading.json`, `timing.json`, and `provenance.json`, run:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py aggregate /path/to/iteration-N --candidate with_skill --baseline old_skill --pretty --output /path/to/iteration-N/benchmark.json
```

The aggregator compares the discovered `eval-*` directories, assertion texts,
and run provenance with `evaluation-plan.json` fail-closed. It requires the
plan at the iteration's parent, exact full-suite coverage, both configurations
for every eval, frozen assertion sets, valid provenance, one candidate package
identity within the iteration, and the frozen plan, baseline, and environment
identities. Any evidence mismatch makes `facts.evidence_complete` and its
compatibility alias `facts.complete` false, sets `facts.delta` to `null`, and
leaves `facts.gate.status` as `indeterminate`.

The script gives each eval equal weight and reports the number of evals, mean,
and standard deviation for per-eval assertion pass rate, time, and tokens. It
does not pool assertions across evals, so an eval with more assertions receives
the same pass-rate weight as one with fewer. Standard deviation is `null` for
one eval. It reports incomplete or malformed runs rather than silently
excluding them. It rejects symbolic links, junctions, and other
reparse points on the run and output paths it reads or writes. Aggregate output
must stay inside that same root. The first write refuses to clobber an existing
entry; use `--force` only to atomically replace an existing ordinary file.
Output links, redirecting parent paths, and special files are always rejected.
On platforms without directory-relative file operations, do not mutate the
iteration concurrently with publication; those races can only be checked on a
best-effort basis. Use `--output -` when no report file should be created.

The JSON result classifies every assertion in a complete matched pair:

- `candidate_only`: the candidate passes and the baseline fails;
- `baseline_only`: the baseline passes and the candidate fails;
- `both_pass`: both configurations pass;
- `both_fail`: both configurations fail.

Use `facts.assertion_summary` for totals and `facts.assertion_analysis` for the
per-eval evidence. Only complete pairs with identical assertion text sets
contribute. When `facts.evidence_complete` is false, the analysis may be partial
and is not regression evidence. These are diagnostic assertion-instance counts,
not a new quality score; `both_fail` and `baseline_only` become gate failures
only when the frozen acceptance contract makes them material.

With complete evidence, the aggregator evaluates every configured acceptance
check and sets `facts.gate.status` to `passed` or `failed`. A failed gate keeps
`facts.evidence_complete=true`, preserves `facts.delta` and assertion analysis,
adds `aggregate.acceptance_failed`, and exits `1`. Invalid or incomplete
evidence also exits `1`, but the gate is `indeterminate`; complete evidence
with a passed gate exits `0`. The fatal exit-`2` class is enumerated in every
subcommand's `--help`.

Use `facts.coverage`, `facts.provenance`, and `facts.identities` to retain the
validated campaign bindings with the benchmark. Aggregation proves consistency
of this iteration's declared identities; it does not independently derive a
package digest, prove that a declared identity is truthful, or establish
cross-iteration consistency.

This is deterministic classification, not an automatic eval-quality verdict.
Use the frozen success bar, retained outputs, and transcripts to judge assertion
quality, explain variance, or identify a material cost anomaly.

Interpret quality and cost separately. Inspect:

- assertions that improve only with the candidate;
- assertions that always pass or always fail in both configurations;
- high variance, which can indicate flaky tests or ambiguous instructions;
- time and token outliers, using transcripts to find the cause.

Report quality, time, and tokens separately.

## Iterate

When the same review request authorizes remediation, use failed assertions,
available feedback, and transcripts to revise the supported root cause directly
in the original target. Finish every edit; starting its next preflight freezes
that target revision. Then rerun the entire suite in `iteration-N+1`, not only
the failures. Otherwise, report the supported revision without editing.
Succeed when the frozen criteria pass. At the iteration limit, stop and report
every unmet criterion rather than weakening the bar.

## Source

- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)
