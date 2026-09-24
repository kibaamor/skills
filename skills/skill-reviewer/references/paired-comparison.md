# Paired comparison

Use this branch only for a comparative claim, a regression check, or evidence
that a revision improves behavior. Read the
[evaluation artifact contract](evaluation-artifact-contract.md) before creating
the workspace or running either configuration.

The authorization and untrusted-target rules in `SKILL.md` remain in force. A
request to inspect existing results does not authorize new execution. Run target
behavior only when the review request separately authorizes behavioral
evaluation and the entry point, reachable helpers, fixtures, network behavior,
credentials, and external side effects have been checked as required there.
Loading target instructions into an isolated worker does not authorize running
code bundled or referenced by the target; do that only when the user explicitly
authorizes code execution and the required inspection finds no undeclared side
effects.

## Start with a small real test set

Begin with two or three realistic cases. Vary wording and detail, and include a
malformed, boundary, or ambiguous case when useful. Each case needs a user
prompt, a human-readable expected outcome, and any required inputs.

Use the target's existing eval definitions as read-only input. Put every new or
modified definition and fixture in the isolated evaluation workspace so review
findings are formed without mutating the target.

Observe initial outputs before freezing detailed assertions. This prevents the
test from encoding guesses about how a good answer must look. Turn the observed
success conditions into objective, wording-robust assertions: use scripts for
mechanical facts and a model or human reviewer for semantic qualities.

## Freeze the comparison before running it

Write the evaluation plan and acceptance bar before the first paired run. Freeze
the prompts, inputs, output contracts, assertion texts, environment,
configuration identities, accepted quality and cost deltas, and iteration
limit. Changing any of them starts a new campaign rather than quietly moving the
bar.

Use three iterations when the user supplies no other limit.

Finish the candidate revision before its boundary preflight. Keep that exact
package revision unchanged through the iteration, and bind every retained run
to its package, plan, case, configuration, and environment identities. Follow
the field, digest, layout, and provenance rules in the artifact contract.

## Run an isolated pair

Give both configurations the same prompt, inputs, output contract, and clean
starting state. Use a fresh context and a unique output directory for each run.
Do not share mutable fixtures or output directories.

When independent workers are available, launch both sides before inspecting
either result. Otherwise run them sequentially in fresh contexts and do not let
the first result change the second task.

- For a new skill, compare `with_skill` with `without_skill`.
- For authorized remediation, preserve the pre-edit target as an isolated,
  read-only baseline and compare it with the frozen revised target.

For `without_skill`, retain harness evidence that the package was withheld. Its
package identity may equal the candidate identity because the measured change
is whether that exact package was loaded.

If authorization, isolation, observability, or budget prevents a fair pair,
report the limitation instead of presenting a simulated benchmark.

## Grade and review both sides

Grade both sides against the same frozen assertions and require concrete
evidence for every result. Do not give ambiguous output the benefit of the
doubt. Revisit assertions that both sides always pass, both always fail, or
cannot be checked from retained output.

Use blinded comparison for holistic qualities such as organization and
usability: record the preference and reasons before revealing the mapping. When
a human reviewer is available, retain their specific feedback or explicit
no-issue result. Otherwise record that human review was not performed; model
judging is not human assurance. Use the host's native safe artifact presentation
instead of building a one-off viewer.

## Aggregate and interpret

After every planned run has the grading, timing, and provenance evidence defined
by the artifact contract, invoke its documented aggregate command. Treat any
coverage, assertion, identity, provenance, or completeness mismatch as
incomplete comparative evidence. Do not calculate or report a trusted delta
from an incomplete pair.

Interpret quality, time, and tokens separately. Inspect:

- assertions passed only by the candidate or only by the baseline;
- assertions that pass or fail in both configurations;
- dispersion and outliers, without confusing cross-case differences with
  repeated-run instability;
- transcript evidence explaining material time or token differences.

Aggregation is deterministic classification, not an automatic judgment that
the evals are good. Advance to `behavior: paired_comparison_observed` only when
the complete retained evidence is bound to the reviewed package and frozen
campaign.

## Iterate only within authorization

When the same request authorizes remediation, use failed assertions, review
feedback, and traces to fix reusable root causes in the original target. Finish
the edit, establish the next revision identity, and rerun the whole suite in a
new iteration. Do not rerun only the failures.

Stop when the frozen acceptance criteria pass or the iteration limit is reached.
At the limit, report every unmet criterion rather than weakening the bar. In
read-only mode, report the comparison and proposed corrections without editing
the target.

## Source

- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills)
