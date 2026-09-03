# Project Knowledge Skill

Generate or refresh compact, evidence-backed repository knowledge for coding agents. The skill selects only documents justified by repository evidence and keeps operating guidance, domain language, architecture, and source navigation in their proper owners.

## Use The Skill

Invoke `/project-knowledge` in VS Code Chat, or ask Copilot to generate, refresh, or synchronize project knowledge for the current repository. For a source-navigation-only update, explicitly request a `CODE-MAP.md`-only refresh.

Depending on the repository, the skill may create or update:

- `AGENTS.md`
- `CONTEXT.md` or `CONTEXT-MAP.md` with context-local glossaries
- `ARCHITECTURE.md`
- `CODE-MAP.md`

See [SKILL.md](./SKILL.md) for the workflow and [document contracts](./references/document-contracts.md) for document selection and ownership rules.

## Layout

- `SKILL.md`: agent workflow and completion contract.
- `references/`: evidence, document, verification, and quality rules.
- `scripts/validate-knowledge.mjs`: deterministic Markdown link and heading validator.
- `scripts/run-evals.mjs`: Waza runner for behavior and trigger evaluations.
- `evals/evals.json`: behavior scenarios and semantic expectations.
- `evals/trigger-evals.json`: positive and negative invocation scenarios.
- `evals/files/`: repository fixtures supplied to behavior scenarios.

## Run Tests

From the repository root, run the deterministic unit tests:

```bash
node --test \
  ./skills/project-knowledge/scripts/validate-knowledge.test.mjs \
  ./skills/project-knowledge/scripts/run-evals.test.mjs
```

Validate generated knowledge documents by passing only files that exist:

```bash
node ./skills/project-knowledge/scripts/validate-knowledge.mjs \
  <repository-root> AGENTS.md CONTEXT.md ARCHITECTURE.md CODE-MAP.md
```

The validator exits with code `0` when all local links resolve with exact casing and headings are valid. It prints each violation and exits with code `1` otherwise.

## Run Evaluations

Behavior evaluations execute an agent against repository fixtures and use a prompt grader. Trigger evaluations check whether the skill should be selected. They require [Waza](https://github.com/microsoft/waza) and an authenticated GitHub Copilot installation.

List available scenarios without calling a model:

```bash
node ./skills/project-knowledge/scripts/run-evals.mjs --list
```

Run one scenario while developing:

```bash
node ./skills/project-knowledge/scripts/run-evals.mjs \
  --task behavior-04 --model gpt-5-mini
```

Run a group or the complete suite:

```bash
# All trigger scenarios
node ./skills/project-knowledge/scripts/run-evals.mjs --tags trigger

# All behavior scenarios
node ./skills/project-knowledge/scripts/run-evals.mjs --tags behavior

# Complete suite
node ./skills/project-knowledge/scripts/run-evals.mjs
```

Additional arguments are forwarded to `waza run`; use `--trials 2` for repeated runs or `--parallel --workers 2` when concurrency is appropriate. The complete suite invokes models for every scenario, so prefer one task before running all scenarios.

## View Results

The runner prints a summary and the result paths. It replaces previous outputs under `evals/results/`:

- `latest.json`: complete scores, grader feedback, token usage, tool calls, and transcript.
- `latest.junit.xml`: JUnit report when Waza produces one.

Generated result files are ignored by Git. On a failed behavior scenario, inspect `tasks[].runs[].validations` in `latest.json`; the prompt grader response explains which expectations or failure conditions were observed. For a negative trigger scenario, the score is trigger similarity and passes when it is below the configured threshold, so it is not a completion-quality percentage.

## Add An Evaluation

Add behavior coverage to `evals/evals.json` and place its repository fixture in `evals/files/`. Add invocation coverage to `evals/trigger-evals.json`. Keep expectations observable and failure conditions specific, then run the conversion test and the new scenario before running the full suite.
