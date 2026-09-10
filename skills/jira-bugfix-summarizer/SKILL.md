---
name: jira-bugfix-summarizer
description: "Summarize an already fixed Jira bug for stakeholders; use for impact/root-cause/fix/validation summaries, not diagnosis, implementation, or Jira updates."
---

# Bugfix Summarizer

Write a stakeholder-facing summary for a Jira bug that is already fixed.

Only read supplied issue details, links, or resources. Do not create, update, transition, comment on, attach to, or write to Jira, repos, files, or external systems. If the user asks for diagnosis, implementation, or updates, state that this skill only summarizes fixed bugs and stop.

Preserve literal identifiers exactly: Jira keys, URLs, commits, change IDs, branches, versions, environments, config keys, function names, and error codes.

## Workflow

1. Confirm fit. Done when fixed status is supplied or the user confirms it; if not fixed, stop.
2. Gather facts. Done when these are known, explicitly unavailable, or user-approved to omit after one bundled clarification question: symptom, impact scope, root cause, fixed behavior, client-update requirement, fix records, validation.
3. Load `references/change-records.md` before writing `Fix Records`. Done when every listed record is an effective changed result, not a review/process artifact.
4. Draft the summary. Done when it covers impact, root cause, fix, client update requirement, fix records, and validation.
5. Self-check. Done when every claim is supported and validation is labelled correctly.

## Output

Use this structure unless the user asks for another format:

```markdown
## Bugfix Summary

<Observed issue and fixed outcome in one short paragraph.>

### Impact Scope

<Affected feature, entry point, platform/environment, workflow stage, and confirmed unaffected adjacent flows.>

### Root Cause

<Business/process cause first. Add technical anchors only if they support the explanation.>

### Fix

<What changed, where it changed, new behavior, and whether a client update/new build is required.>

### Fix Records

<Effective records only, using `references/change-records.md`.>

### Validation

<Start with `Validated:` only for confirmed validation; otherwise `Suggested validation:`. Include prerequisites, steps, expected result, reverse/recovery checks, and regression scope.>
```

## Rules

- Ask at most one bundled clarification question for missing required facts.
- If the user approves omissions, mark unavailable facts explicitly; do not invent them.
- Explain user-visible impact before implementation detail.
- Use neutral system wording, not blame.
- Do not claim tests, deployment, logs, or validation passed unless confirmed.
- Keep validation executable: prerequisite, action, expected result.
- Separate failing paths from already-correct paths when it helps validation.
- Do not list merge requests, reviews, pipeline runs, draft branches, or pending changes as fix records.
