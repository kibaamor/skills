# Evaluation artifact contract

Use this contract when authoring, validating, retaining, or aggregating evidence
for the paired-comparison workflow. Keep generated campaign data outside the
published target skill package.

## Evaluation definitions

Store new or modified definitions under the isolated evaluation workspace. Use
the target's `evals/evals.json` only as read-only input.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": "descriptive-id",
      "prompt": "A realistic user request with paths and context",
      "expected_output": "Observable characteristics of success",
      "files": ["<input-file-path>"],
      "assertions": ["An objective frozen assertion"]
    }
  ]
}
```

The root accepts only `skill_name` and `evals`. A case accepts only `id`,
`prompt`, `expected_output`, `files`, and `assertions`. Names and IDs are
compared after trimming surrounding whitespace. Fixture paths are relative to
the definition workspace when `--skill-root` identifies the immutable target.
Validate before running:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py validate-evals /path/to/example-skill-workspace/evals/evals.json --skill-root /path/to/example-skill --pretty
```

## Frozen evaluation plan

Write `evaluation-plan.json` at the workspace root before the first paired run.
This is the minimum machine-readable subset; additional frozen prompts, inputs,
output contracts, bars, and iteration-limit fields are permitted.

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

`schema_version` is the integer `1`. Package identities use `sha256:` followed
by 64 lowercase hexadecimal digits. Configuration names equal the aggregate
CLI arguments. Eval IDs and directories are unique; directories are one path
component beginning with `eval-`; assertion strings are non-empty and unique
after trimming. The planned directory set exactly matches the iteration's
discovered `eval-*` directories. All other shown strings are non-empty.

`acceptance` is an allowlist. `min_candidate_pass_rate` and
`min_pass_rate_delta` are required numbers in `[0, 1]` and `[-1, 1]`.
`max_time_seconds_delta` and `max_tokens_delta` are optional non-negative
numbers; `max_baseline_only` is an optional non-negative integer that caps
baseline-only assertion instances across complete pairs. Unknown acceptance
fields are rejected. Bounds are inclusive, with one-unit-in-the-last-place
tolerance for floating-point boundary arithmetic. Omitting an optional maximum
leaves that metric outside the automated gate, so retain and report it
separately.

Changing an evaluation input, environment, assertion, or acceptance bar starts
a new campaign. The candidate identity may change between iterations; do not
rewrite the plan to record it.

After freezing the plan, calculate `plan_identity` as SHA-256 over its exact
UTF-8 bytes. Whitespace and key order therefore affect the identity. Do not add
the digest to the plan because that would make it self-referential.

## Package and provenance binding

Obtain package identities only from a trusted static preflight where
`summary.truncated` is `false`, `facts.package_inventory_complete`,
`facts.package_digest_complete`, and `facts.text_inspection_complete` are
`true`, and `facts.package_identity` contains a `sha256:` identity. The
`skill-package-manifest-v1` digest covers
the paths and bytes of ordinary package files except regenerated cache
artifacts. Its per-file and whole-package budgets appear in `facts.limits`;
`package_digest_bytes` counts ordinary-file contents, not manifest framing.
After a digest failure that count may be partial. The aggregator validates
declared identity syntax and consistency; it does not re-read a package to prove
that a declaration is truthful.

Starting preflight is the revision freeze boundary. Keep that revision
unchanged through its report. Compute a pre-edit baseline snapshot identity once
and reuse it for every baseline run. Use one candidate preflight identity for
every candidate run in an iteration.

Write `provenance.json` beside each configuration's grading and timing files:

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

The schema, plan digest, campaign, eval, configuration, and environment bind to
the plan and directory being aggregated. The baseline package identity equals
the frozen plan value. A candidate identity may differ between iterations but
is identical across all candidate runs in one iteration.

## Workspace and per-run artifacts

Do not overwrite prior iterations:

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
    │   └── old_skill/            # or without_skill
    │       ├── outputs/
    │       ├── grading.json
    │       ├── provenance.json
    │       └── timing.json
    ├── feedback.md
    └── benchmark.json
```

Capture transcripts when the harness exposes them. Immediately retain timing
data reported by each worker:

```json
{"total_tokens": 84852, "duration_ms": 23332}
```

Store grading results as:

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

Every result has concrete evidence, including failures. Both configurations use
the exact frozen assertion texts.

In `feedback.md`, record one entry per eval and review lane with the eval ID,
reviewer kind (`human` or `model`), review status (`performed` or
`not_performed`), and blinding status (`blinded`, `unblinded`, or
`not_applicable`). A performed review also records its preference (`A`, `B`,
`tie`, or `inconclusive`), reasons or an explicit no-issue result, and the A/B
mapping. For blinded review, record preference and reasons before appending the
mapping. A review not performed records its reason, uses `not_applicable`, and
omits preference and mapping.

## Aggregate output and gate

After every run has grading, timing, and provenance, run:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py aggregate /path/to/iteration-N --candidate with_skill --baseline old_skill --pretty --output /path/to/iteration-N/benchmark.json
```

The aggregator requires the plan at the iteration's parent, exact full-suite
directory coverage, both selected configurations for every eval, identical
frozen assertion sets, valid provenance, one candidate package identity within
the iteration, and matching plan, baseline, and environment identities.

Any evidence error makes `facts.evidence_complete` and its compatibility alias
`facts.complete` false, sets `facts.delta` to `null`, and leaves
`facts.gate.status` as `indeterminate`. Malformed or missing runs are reported,
not silently excluded.

Each eval receives equal weight. The result reports the number of evals, mean,
and standard deviation for per-eval assertion pass rate, time, and tokens; it
does not pool assertions across evals. Standard deviation is `null` for one
eval.

For each complete matched pair, `facts.assertion_summary` and
`facts.assertion_analysis` classify assertion instances as:

- `candidate_only`: candidate passes and baseline fails;
- `baseline_only`: baseline passes and candidate fails;
- `both_pass`: both configurations pass;
- `both_fail`: both configurations fail.

These counts are diagnostic, not a new quality score. When evidence is
incomplete, any partial analysis is not regression evidence.

With complete evidence, every configured acceptance check produces
`facts.gate.status` of `passed` or `failed`. A failed gate preserves complete
evidence, deltas, and assertion analysis, adds `aggregate.acceptance_failed`,
and exits `1`. Invalid or incomplete evidence also exits `1`, with an
indeterminate gate. A complete passed gate exits `0`; fatal CLI, filesystem,
JSON, or output failures exit `2` as documented in command help.

Aggregate output must remain inside the iteration root. The first write does
not clobber an existing entry; `--force` replaces only an ordinary file.
Symlinks, redirecting parents, special files, and reparse points are rejected.
On platforms without directory-relative operations, do not mutate the
iteration concurrently with publication. Use `--output -` when no file should
be created.

Use `facts.coverage`, `facts.provenance`, and `facts.identities` to retain the
validated campaign bindings. Aggregation proves consistency of declared
identities in this iteration; it does not derive the digest independently or
establish cross-iteration consistency.
