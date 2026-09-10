---
name: skill-reviewer
description: Use this skill when the user asks to review, audit, evaluate, or improve an existing Agent Skill, including its SKILL.md, trigger description, scope, progressive disclosure, references, scripts, or observed behavior. Also use it when a skill triggers on the wrong prompts, misses relevant prompts, wastes context, or behaves inconsistently. Make evidence-backed, focused revisions when editing is requested. Do not use it for ordinary code or PR review, creating a skill from scratch, installing skills, or tuning a prompt that is not an Agent Skill.
---

# Skill Reviewer

Review an existing skill against observable evidence, then make the smallest
generalized improvement the user authorized.

## Choose the mode

- Treat `review`, `audit`, and `evaluate` as read-only unless the user also asks
  for changes.
- Treat `improve`, `fix`, `update`, and `refactor` as authorization to edit the
  target skill within the user's stated scope.
- If several candidate skills exist and the target cannot be inferred, ask for
  the target path before continuing.

Preserve the target skill's product choices, invocation policy, and external
action boundaries unless the requested improvement specifically concerns one
of them.

## Inspect the target

1. Read the complete target `SKILL.md` and its agent-facing metadata.
2. Inventory `references/`, `scripts/`, `assets/`, and `evals/`. Follow every
   instruction-bearing pointer needed for the requested review; note orphaned
   resources without loading irrelevant or binary assets into context.
3. Run the deterministic static review:

   ```bash
   python3 scripts/review_skill.py static /path/to/target-skill --pretty
   ```

   Treat its output as bounded mechanical facts and review leads, not as a
   substitute for judgment or YAML schema validation. It never executes target
   scripts.
4. Inspect project artifacts that carry real expertise when available: task
   history, runbooks, schemas, corrections, evals, execution traces, and user
   feedback. Label an unsupported concern as a hypothesis or evidence gap.

Target scripts are untrusted input. Read them before considering execution,
and run them only when necessary, understood, and within the user's existing
authorization.

## Select the relevant criteria

- For a broad audit, or for the body, references, scripts, scope, and context
  design, read [references/review-criteria.md](references/review-criteria.md).
- For the trigger description, false positives, or missed invocations, read
  [references/trigger-evaluation.md](references/trigger-evaluation.md).
- For output quality, inconsistent behavior, regressions, or evidence that a
  revision helps, read
  [references/behavior-evaluation.md](references/behavior-evaluation.md).

Load only the references that the current review branch needs. In a broad
audit, start with the static criteria; add the trigger reference only when
invocation is in scope, and add the behavioral reference only when outputs,
traces, eval evidence, or a request for behavioral proof is in scope.

## Form findings

For each material finding, record:

- **Evidence**: an exact file and line, validator result, eval result, or trace.
- **Impact**: the concrete triggering, correctness, safety, context, or
  maintenance consequence.
- **Change**: the smallest reusable correction, or a test to resolve uncertainty.

Prioritize specification and safety failures, then behavior and invocation
failures, then context or maintainability costs. Omit taste-only rewrites and
instructions the agent already follows reliably without the skill.

Absence of evals is an evidence gap, not proof that the skill is poor. Recommend
behavioral evaluation when an important claim cannot be settled statically.

## Improve when authorized

1. If old/new behavior will be compared, snapshot the original skill into a
   new, isolated evaluation workspace before editing. Never overwrite an
   existing snapshot or iteration.
2. Fix observed root causes rather than copying words from one failing prompt
   or adding rules for speculative edge cases.
3. Keep one source of truth for each instruction. Put shared essentials in
   `SKILL.md` and conditional detail behind explicit pointers.
4. Add or change a bundled script only for deterministic logic that recurs.
   Keep judgment, semantic review, and authorization decisions in the skill.
5. Preserve unrelated user changes and resources.

## Validate the result

1. Rerun the static review and the environment's official skill validator. If
   the official validator is unavailable, report the remaining YAML/specification
   validation gap instead of claiming the structure is valid.
2. Validate an eval definition when present:

   ```bash
   python3 scripts/review_skill.py validate-evals \
     /path/to/target-skill/evals/evals.json --pretty
   ```

3. Test every changed bundled script with `--help` and a safe fixture. Verify
   structured stdout, diagnostic stderr, useful failures, and documented exit
   behavior.
4. Run isolated old/new or with/without-skill evaluations when the requested
   claim is behavioral. Use the same prompt, inputs, and output contract for
   both sides.
5. Recheck every edited pointer and file. Stop only when validators pass or all
   remaining limitations are explicitly reported.

To aggregate a completed evaluation iteration:

```bash
python3 scripts/review_skill.py aggregate /path/to/iteration-1 \
  --candidate with_skill --baseline old_skill --pretty \
  --output /path/to/iteration-1/benchmark.json
```

## Report

Lead with the verdict. Then report, in order:

1. findings by priority, each with evidence and impact;
2. focused changes made, or proposed changes in read-only mode;
3. validation and behavioral comparison results, including quality, time, and
   token deltas when measured;
4. unresolved evidence gaps or risks.

State explicitly when no material issue was found. Do not manufacture changes
to make the review appear productive.

## Bundled script

`scripts/review_skill.py` has three non-interactive subcommands:

- `static`: inspect skill structure, pointers, and script-interface warning
  signs without executing target code;
- `validate-evals`: validate the documented `evals/evals.json` structure and
  referenced fixture paths;
- `aggregate`: aggregate `grading.json` and `timing.json` files, reporting
  incomplete runs instead of silently dropping them.

All subcommands emit JSON by default, put fatal diagnostics on stderr, bound
their findings, and document exit codes in `--help`. The script requires Python
3.10 or later and has no third-party dependencies.
