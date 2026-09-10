# Trigger description evaluation

Use this reference when a description is being reviewed or changed, or when
false-positive or missed invocations are reported.

## Review the description

The description is the always-loaded routing pointer. It should:

- use imperative language such as `Use this skill when ...`;
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
queries. Both sets need positives and negatives. Use only training failures to
revise the description.

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

1. Evaluate the current description on both fixed splits.
2. Diagnose training failures. Generalize the missing intent for false
   negatives; sharpen the adjacent-task boundary for false positives.
3. Revise concepts, not literal words copied from failed queries. Keep the
   description under the character limit.
4. Re-evaluate both splits, but continue to hide validation examples and
   results from the revision step.
5. Select the version with the best validation performance; it may be an earlier
   iteration. About five rounds is usually enough before reassessing labels and
   query difficulty.
6. Confirm the selected description on 5-10 new positive and near-miss queries
   that played no role in optimization.

Report false-positive and false-negative rates separately. A single accuracy
number can hide a description that catches everything or nothing.

## Common boundaries for a reviewer skill

For a skill-reviewing skill, useful negative near misses include ordinary code
or PR review, creating a brand-new skill, installing a skill, debugging one
helper in isolation, and general prompt tuning. They become positives only when
the user's intent is to assess or improve an existing Agent Skill as a unit.

## Source

- [Optimizing skill descriptions](https://agentskills.io/skill-creation/optimizing-descriptions)
