# Trigger description evaluation

Use this reference when a description is being reviewed or changed, or when
false-positive or missed invocations are reported.

## Review the description

The description is the always-loaded routing pointer. It should:

- front-load the user intent with an action phrase;
- describe user intent, not internal implementation;
- cover implicit phrasings of the same intent without expanding the skill's
  actual scope;
- name boundaries with adjacent tasks when those tasks are plausible near
  misses;
- remain concise and under 1,024 characters.

A longer list of synonyms rarely fixes routing. Express distinct intent
branches and meaningful boundaries.

## Build realistic query sets

Start with about 20 labeled queries: 8-10 expected to trigger and 8-10 expected
not to trigger. Adjust the count when cost or domain breadth warrants it.

Positive queries should vary:

- formal, casual, abbreviated, and occasionally mistyped phrasing;
- explicit domain names versus implicit descriptions of the need;
- terse requests versus paths, filenames, data, and personal context;
- simple tasks versus the intent embedded in a larger workflow.

Negative queries should be **near misses** that share vocabulary or artifacts
but require an adjacent capability. Obviously unrelated prompts do not test the
description's precision.

Keep a fixed, stratified split of roughly 60% training and 40% validation
queries. Treat a validation share from 30% through 50% as the suggested range;
the validator emits only a warning outside it because split balance is a review
heuristic, not proof of routing quality. Both sets need positives and negatives.
Use only training failures to revise the description.

Validate the query file before running routing experiments:

```text
python3 /absolute/path/to/skill-reviewer/scripts/review_skill.py validate-triggers /path/to/target-skill/evals/trigger_queries.json --pretty
```

This validates labels, uniqueness, and split composition. It does not execute
the queries or prove invocation behavior.

## Measure invocation

Run every query in a clean context with the target skill installed and use the
client's trace or tool history to determine whether `SKILL.md` was loaded.
Record the client, model, skill version, and detection method.

Because invocation is nondeterministic, three runs per query are a useful
starting point. Compute:

```text
trigger_rate = triggered_runs / total_runs
```

An initial threshold of 0.5 is reasonable: a positive passes at or above the
threshold and a negative passes below it. Treat both the run count and threshold
as experimental choices, not specification constants.

Stop a run early only when the client makes invocation or non-invocation
observable without changing the test semantics.

## Optimize without overfitting

1. Before revising, freeze the query set, runs per query, trigger threshold,
   acceptable false-positive and false-negative rates, client, model, detection
   method, harness and installation setup, and iteration limit. Keep validation
   queries outside the revising agent's context through an independent harness
   or evaluator. If no real context boundary is available, label the set
   `unblinded` rather than claiming holdout evidence.
2. Evaluate the current description on the training split. Diagnose those
   failures, generalize the missing intent for false negatives, and sharpen the
   adjacent-task boundary for false positives.
3. Revise concepts, not literal query wording. Run every candidate on the
   training split with the frozen protocol, diagnose its failures, and save it.
   Create each revision in a new isolated candidate copy and freeze it before
   routing runs. Stop when the training bar passes or at the fixed iteration
   limit; about five candidates is a useful default.
4. After candidates are frozen, have the independent evaluator run one
   validation campaign for each candidate using the frozen per-query run count
   and threshold. Select a candidate that meets both frozen error-rate bars
   without another revision round; an earlier candidate may win. If none meets
   them, report the unmet bar rather than claiming the description was
   optimized.
5. Confirm a candidate that passes both bars on 5-10 new positive and near-miss
   queries that influenced neither revision nor selection. If confirmation
   misses the bars, report it and start a new campaign before further revision.

Report false-positive and false-negative rates separately. A single accuracy
number can hide a description that catches everything or nothing.

## Source

- [Optimizing skill descriptions](https://agentskills.io/skill-creation/optimizing-descriptions)
