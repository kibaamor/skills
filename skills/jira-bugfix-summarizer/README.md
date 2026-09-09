# Jira Bugfix Summarizer Skill

Summarize an already diagnosed and fixed Jira issue for non-technical stakeholders. The skill writes the final summary in Chinese and focuses on user impact, process-level root cause, fixed behavior, effective fix records, and validation suggestions.

## Use The Skill

Invoke `/jira-bugfix-summarizer` in VS Code Chat, use `$jira-bugfix-summarizer` where the agent expects skill references, or ask Copilot to summarize an already fixed Jira issue for business, product, or QA readers.

Provide the Jira key, title, status, user-visible symptom, impact scope, root cause, fix behavior, effective fix records, and validation context when available. If only process records such as PRs, reviews, pipelines, or app store submissions are available, the skill should ask for the authoritative effective fix record before producing the final summary.

See [SKILL.md](./SKILL.md) for the workflow and [fix record rules](./references/change-records.md) for what belongs in `修复记录`.

## Layout

- `SKILL.md`: agent workflow, required summary structure, and writing constraints.
- `references/change-records.md`: rules for selecting only effective changed-result records.
- `scripts/run-evals.mjs`: Waza runner for behavior and trigger evaluations.
- `evals/evals.json`: behavior scenarios and semantic expectations.
- `evals/trigger-evals.json`: positive and negative invocation scenarios.

## Run Tests

From the repository root, run the deterministic unit test:

```bash
node --test ./skills/jira-bugfix-summarizer/scripts/run-evals.test.mjs
```

The test verifies that behavior and trigger evaluation configs convert into Waza tasks with unique IDs and the expected grader prompts.

## Run Evaluations

Behavior evaluations execute an agent against fixed Jira summary scenarios and use a prompt grader. Trigger evaluations check whether the skill should be selected. They require [Waza](https://github.com/microsoft/waza) and an authenticated GitHub Copilot installation.

List available scenarios without calling a model:

```bash
node ./skills/jira-bugfix-summarizer/scripts/run-evals.mjs --list
```

Run one scenario while developing:

```bash
node ./skills/jira-bugfix-summarizer/scripts/run-evals.mjs \
  --task behavior-01 --model gpt-5-mini
```

Run a group or the complete suite:

```bash
# All trigger scenarios
node ./skills/jira-bugfix-summarizer/scripts/run-evals.mjs --tags trigger

# All behavior scenarios
node ./skills/jira-bugfix-summarizer/scripts/run-evals.mjs --tags behavior

# Complete suite
node ./skills/jira-bugfix-summarizer/scripts/run-evals.mjs
```

Additional arguments are forwarded to `waza run`; use `--trials 2` for repeated runs or `--parallel --workers 2` when concurrency is appropriate. The complete suite invokes models for every scenario, so prefer one task before running all scenarios.

## View Results

The runner prints a summary and the result paths. It replaces the previous latest outputs under `evals/results/`:

- `latest.json`: complete scores, grader feedback, token usage, tool calls, and transcript.
- `latest.junit.xml`: JUnit report when Waza produces one.

Generated result files are ignored by Git. On a failed behavior scenario, inspect `tasks[].runs[].validations` in `latest.json`; the prompt grader response explains which expectations or failure conditions were observed. For a negative trigger scenario, the score is trigger similarity and passes when it is below the configured threshold, so it is not a completion-quality percentage.

## Add An Evaluation

Add behavior coverage to `evals/evals.json`. Add invocation coverage to `evals/trigger-evals.json`. Keep expectations observable, make failure conditions specific, then run the conversion test and the new scenario before running the full suite.
