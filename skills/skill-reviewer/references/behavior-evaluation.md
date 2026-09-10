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

```bash
python3 scripts/review_skill.py validate-evals \
  /path/to/example-skill/evals/evals.json --pretty
```

Observe the first outputs before adding detailed assertions. This keeps the
initial test from encoding guesses about how a good solution must look.

## Use an isolated paired comparison

Every run starts with a clean context and a unique output directory. Give both
sides the identical prompt, inputs, and output contract.

- For a new skill, compare `with_skill` with `without_skill`.
- For an improvement, snapshot the untouched target first and compare
  `with_skill` with `old_skill`.

Use this layout without overwriting prior iterations:

```text
<skill>-workspace/
└── iteration-N/
    ├── eval-<case>/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   ├── grading.json
    │   │   └── timing.json
    │   └── old_skill/              # or without_skill
    │       ├── outputs/
    │       ├── grading.json
    │       └── timing.json
    ├── feedback.json
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

## Add and grade assertions

After inspecting initial outputs, add assertions that are objective,
observable, and robust to wording. Use scripts for mechanical facts such as
JSON validity or file dimensions; use an LLM judge for semantic claims.

Every result needs concrete evidence:

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
hide which output is the candidate. Human-review every case and save specific,
actionable feedback; an empty feedback string means no issue was found.

## Aggregate and interpret

After every run has both `grading.json` and `timing.json`, run:

```bash
python3 scripts/review_skill.py aggregate /path/to/iteration-N \
  --candidate with_skill --baseline old_skill --pretty \
  --output /path/to/iteration-N/benchmark.json
```

The script gives each run equal weight and reports the number of runs, mean,
and standard deviation for assertion pass rate, time, and tokens. Standard
deviation is `null` for one run. It reports incomplete or malformed runs rather
than silently excluding them.

Interpret quality and cost separately. Inspect:

- assertions that improve only with the candidate;
- assertions that always pass or always fail in both configurations;
- high variance, which can indicate flaky tests or ambiguous instructions;
- time and token outliers, using transcripts to find the cause.

Do not collapse quality, time, and tokens into one opaque score.

## Iterate

Combine failed assertions, human feedback, and transcripts to identify root
causes. Generalize the correction, keep the skill lean, explain why where
judgment is needed, and bundle only repeated deterministic work.

Apply the focused revision, then rerun the entire suite in `iteration-N+1`, not
only the failures. Stop when results meet the user's bar, human feedback is
consistently empty, or further iterations show no meaningful improvement.

## Source

- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)
