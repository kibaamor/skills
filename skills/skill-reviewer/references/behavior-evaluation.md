# Behavioral evaluation

Use this reference when reviewing output quality, investigating inconsistent
behavior, or verifying that an important revision helps.

## Start with a small real test set

Begin with two or three cases. Each case contains a realistic user prompt, a
human-readable expected outcome, and optional input files. Vary wording and
detail, and include at least one malformed, boundary, or ambiguous case.

Store definitions in the target skill's `evals/evals.json`:

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

Validate it before running:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py validate-evals /path/to/example-skill/evals/evals.json --pretty
```

Observe the first outputs before adding detailed assertions. This keeps the
initial test from encoding guesses about how a good solution must look.

## Set the success bar

Turn the pilot outputs into assertions that are objective, observable, and
robust to wording. Use scripts for mechanical facts such as JSON validity or
file dimensions; use an LLM judge for semantic claims.

Before the first paired run, write an immutable `evaluation-plan.json` at the
workspace root. Record a campaign identifier; configuration labels, the fixed
baseline identity, and the candidate's starting identity; the execution
environment; case IDs, prompts, inputs, and output contracts; each case's
assertion texts; acceptable quality, time, and token deltas; and a maximum
iteration count. Use three iterations when the user supplies no other limit.
Changing an evaluation input, environment, assertion, or bar starts a new
campaign. The candidate revision is the measured variable, so record its exact
identity in each iteration instead of rewriting the plan.

## Bind evidence to the reviewed package

Attach the configuration identity, exact applicable package identity, frozen
campaign identity, and execution-environment identity to each configuration's
retained provenance. If any required identity cannot be established, report
that limitation and do not present the run as regression evidence for another
version.

## Use an isolated paired comparison

Every run starts with a clean context and a unique output directory. Give both
sides the identical prompt, inputs, and output contract.

When independent workers are available, launch both sides before inspecting
either result. Otherwise run them sequentially in fresh contexts; do not let the
first output change the second run's prompt or contract.

- For a new skill, compare `with_skill` with `without_skill`.
- For authorized remediation, snapshot the untouched target first and compare
  `with_skill` with `old_skill`.

Use this layout without overwriting prior iterations:

```text
<skill>-workspace/
├── evaluation-plan.json
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

Keep fixtures immutable and do not share mutable output directories between
parallel runs. Capture transcripts when the harness exposes them. Immediately
record timing data as:

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

After every run has both `grading.json` and `timing.json`, run:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py aggregate /path/to/iteration-N --candidate with_skill --baseline old_skill --pretty --output /path/to/iteration-N/benchmark.json
```

Before aggregation, compare the discovered `eval-*` directories, assertion
texts, and run provenance with `evaluation-plan.json`. The aggregator checks
each discovered pair and requires matching assertion texts within that pair;
it does not prove full-suite coverage, cross-iteration consistency, or package
identity. Report those checks separately.

The script gives each run equal weight and reports the number of runs, mean,
and standard deviation for assertion pass rate, time, and tokens. Standard
deviation is `null` for one run. It reports incomplete or malformed runs rather
than silently excluding them. It rejects symbolic links, junctions, and other
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
contribute. When `facts.complete` is false, the analysis may be partial and is
not regression evidence. These are diagnostic assertion-instance counts, not a
new quality score; `both_fail` and `baseline_only` do not become findings unless
the frozen success bar makes them material.

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
available feedback, and transcripts to revise the supported root cause, then
rerun the entire suite in `iteration-N+1`, not only the failures. Otherwise,
report the supported revision without editing. Succeed when the frozen criteria
pass. At the iteration limit, stop and report every unmet criterion rather than
weakening the bar.

## Source

- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)
