# Contributing

Thanks for helping improve this collection of Agent Skills. Contributions can
add a skill, refine an existing skill, improve its supporting resources or
evaluations, or fix the repository documentation.

For a substantial or behavior-changing proposal, consider opening an issue
first so the scope and expected behavior can be agreed on before implementation.

## Getting started

Fork the repository, clone your fork, and create a focused branch:

```bash
git clone https://github.com/YOUR-USERNAME/skills.git
cd skills
git switch -c describe-your-change
```

The repository has no root dependency installation step. Validation uses
Python 3.10 or newer and `uvx`; install only the tools needed for the checks
relevant to your change.

## Repository structure

Published skills are direct children of `skills/`:

```text
skills/
  <skill-name>/
    SKILL.md       # required skill definition and instructions
    agents/        # optional client-specific metadata
    references/    # optional supporting documentation
    scripts/       # optional helper scripts
    assets/        # optional static assets
    evals/         # optional evaluation cases and fixtures
```

Skills nested inside an `evals/` directory are test fixtures, not published
install targets.

## Authoring guidelines

- Put each published skill in `skills/<skill-name>/SKILL.md`.
- Use a lowercase, hyphen-separated skill name, and make the frontmatter `name`
  match the directory name exactly.
- Write a precise frontmatter `description` that states when the skill should be
  used and, when useful, which adjacent requests should not trigger it.
- Keep `SKILL.md` focused. Add `references/`, `scripts/`, or `assets/` only when
  the skill workflow uses them, and link bundled files with relative paths.
- Keep bundled scripts non-interactive, document their arguments and exit
  behavior, and separate machine-readable output from diagnostics where
  applicable.
- Update `agents/openai.yaml` when user-facing interface metadata or the default
  invocation changes.
- Add or update `evals/evals.json` and its fixtures when behavior changes. Treat
  source fixtures as immutable during an evaluation and write run output
  elsewhere.
- When adding, removing, or renaming a published skill, update the README skill
  table and single-skill installation examples.

## Validate your changes

There is no single repository-wide test command. Run the checks that apply to
the files you changed and report any check you could not run.

For every changed skill, run the Agent Skills structural validator and the
repository's deterministic static review:

```bash
uvx --from skills-ref agentskills validate skills/SKILL-NAME
python3 -B skills/skill-reviewer/scripts/review_skill.py static skills/SKILL-NAME --pretty
```

Keep the static result as JSON so its inventory, text-inspection, and finding
completeness facts remain visible.

If the skill has `evals/evals.json`, validate its structure:

```bash
python3 -B skills/skill-reviewer/scripts/review_skill.py validate-evals \
  skills/SKILL-NAME/evals/evals.json --format text
```

This validates only the evaluation definition. When comparing revisions, run
both sides with the same inputs and assertions in your evaluation environment.

If the skill has `evals/trigger_queries.json`, validate its labels and split:

```bash
python3 -B skills/skill-reviewer/scripts/review_skill.py validate-triggers \
  skills/SKILL-NAME/evals/trigger_queries.json --format text
```

For trigger changes, run every fixed query through the client and record actual
skill loading. For behavior changes, run the full paired eval set and report any
case that was not executed.

If you change the bundled `skill-reviewer` script or its tests, run:

```bash
python3 -B skills/skill-reviewer/evals/run_tests.py
```

The runner copies `skill-reviewer` to a temporary directory and materializes
its dormant `SKILL.fixture.md` test entries as `SKILL.md` there. The source and
installed skill remain free of nested skill entry points.

To run another test or behavior-evaluation command against the prepared copy,
append `-- COMMAND`. The command runs from the temporary skill root, also
available as `SKILL_REVIEWER_TEST_ROOT`; write retained results outside that
temporary directory.

For any changed script, also exercise `--help`, a safe representative input,
and expected failure behavior. After staging all intended files, inspect the
staged diff and check it for whitespace errors:

```bash
git diff --cached --check
git diff --cached
```

## Pull requests

Keep each pull request focused and include:

- the purpose and scope of the change;
- any change to trigger conditions or observable behavior;
- the validation commands run and their results;
- checks not run, with a short explanation; and
- a linked issue when one exists.

Before opening the pull request, confirm that documentation and interface
metadata match the implementation, relevant evaluation coverage has been
updated, and no generated caches or evaluation run output are included.

By contributing, you agree that your contribution may be distributed under the
repository's [MIT License](LICENSE).
