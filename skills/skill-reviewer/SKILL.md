---
name: skill-reviewer
description: "Review and improve agent skills. Use when asked to audit, critique, rewrite, tighten, or validate a SKILL.md or agent skill against skill-creation best practices: real expertise, scoped activation, context budget, calibrated control, gotchas, templates, checklists, validation loops, and progressive disclosure."
---

# Skill Reviewer

Review an agent skill as an execution tool, not as prose. The skill is good only if it makes the agent behave better on real tasks than the model would behave without it.

## Workflow

1. Identify the skill's job and trigger.
   Completion: you can state in one sentence what task the skill handles, who should invoke it, and which prompts should not invoke it.

2. Inspect the skill package.
   Completion: you have read `SKILL.md` plus any referenced `references/`, `assets/`, `scripts/`, or eval files needed to judge the live instructions.

3. Review against the rubric below.
   Completion: every rubric section has either findings or an explicit `pass`.

4. Improve the skill when asked to edit.
   Completion: the revised skill is shorter or sharper unless the added content fixes a concrete observed gap.

5. Validate the revised skill.
   Completion: frontmatter is valid, activation wording is precise, all pointers name when to load referenced files, and no checklist step lacks a checkable done condition.

## Rubric

### Real Expertise

Look for project-specific or domain-specific material that the model would not reliably know:

- real task traces, user corrections, review feedback, incident notes, runbooks, schemas, configs, or patches
- exact tools, commands, API patterns, data formats, edge cases, and recovery procedures
- concrete gotchas that correct plausible wrong assumptions

Flag generic advice such as "handle errors appropriately", "follow best practices", or "be thorough" unless it is tied to a specific behavior.

### Scope And Invocation

Check whether the skill is one coherent unit of work.

- Too narrow: one normal task needs several tiny skills loaded together.
- Too broad: unrelated branches share one skill and make activation imprecise.
- Model-invoked skills need a `description` with real trigger branches.
- User-invoked skills should set `disable-model-invocation: true`; their description is human-facing and short.

Prefer one clear default trigger over a synonym pile.

### Context Budget

Every always-loaded token must earn its place.

- Cut explanations of concepts the model already knows.
- Cut restatements of package scripts, directory layouts, or config values the agent can cheaply inspect.
- Keep instructions the agent would otherwise get wrong.
- Keep `SKILL.md` focused on what every run needs; move branch-only reference into files such as `references/` or `assets/`.

If a referenced file exists, the main skill must say when to load it. A bare "see references" pointer is a finding.

### Control Calibration

Match strictness to fragility.

- Fragile, destructive, security-sensitive, or order-dependent work needs exact commands, hard boundaries, and stop conditions.
- Flexible review or writing work can give principles and reasons instead of rigid scripts.
- When several approaches work, choose a default and list alternatives only as escape hatches.

Flag menus that present many tools as equal choices without a default.

### Reusable Procedure

The skill should teach an approach for a class of tasks, not a one-off answer.

- Prefer ordered procedures with checkable completion criteria.
- Use templates when output shape matters.
- Use checklists for multi-step workflows.
- Use validation loops: do the work, run the validator or self-check, fix failures, repeat.
- For batch or destructive operations, require plan-validate-execute.

### Gotchas

Gotchas should be concrete corrections to likely mistakes.

Good gotchas mention exact names, commands, fields, endpoints, workflow traps, or environment facts. Weak gotchas merely repeat generic caution.

Keep high-risk gotchas in `SKILL.md` unless the trigger for a reference file is unmistakable.

### Bundled Helpers

If the skill repeatedly asks the agent to parse, validate, transform, or grade the same format, prefer a bundled script over asking each agent run to reinvent the logic.

Flag scripts that are referenced but not given an invocation, expected input, and expected output.

## Output Format

When reviewing only, respond with:

```markdown
## Verdict
[Ship / Needs tightening / Needs rewrite]

## Findings
- [severity] [section]: [specific issue]. Evidence: `[file:line]`. Fix: [concrete change].

## Passes
- [rubric section]: [why it passes]

## Suggested Patch
[brief edit plan or patch summary]
```

Severity:

- `blocker`: likely causes wrong activation, unsafe execution, or unusable output
- `major`: materially reduces reliability or wastes significant context
- `minor`: clarity, pruning, or maintainability improvement

If there are no findings, say `Ship: skill is scoped, specific, and validated.` and include any residual testing gaps.

## Edit Rules

When editing a skill:

- Preserve the author's domain intent; remove generic filler before adding new material.
- Convert vague declarations into procedures, defaults, templates, or gotchas.
- Add hard guardrails only for fragile operations.
- Add references only when the branch is not needed on every run, and include a precise load condition.
- Keep one source of truth for each rule.
- After editing, do a self-review with the rubric and report what changed.

## Self-Check

Before finalizing, verify:

- The frontmatter has `name` and either a precise model-facing `description` or `disable-model-invocation: true`.
- The skill's first screen tells the agent what to do, not just what the skill is about.
- Every workflow step has a visible completion criterion.
- Every referenced file has a condition for loading it.
- The skill contains no generic no-op advice that the model already follows by default.
