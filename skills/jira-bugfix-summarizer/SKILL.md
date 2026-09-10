---
name: jira-bugfix-summarizer
description: "Use when asked to summarize an already fixed Jira bug for stakeholders, including impact, root cause, fix, validation, and effective fix records. Do not use for diagnosing unresolved bugs, implementing fixes, or updating Jira."
---

# Bugfix Summarizer

Create a stakeholder-facing summary of a Jira bug after the fix is already known.

This is a read-only summarization skill. You may read Jira issue details, linked resources, supplied diffs, release notes, logs, comments, and commits that the user authorized you to inspect. Do not create, update, transition, comment on, attach to, or write to Jira, repositories, files, or external systems.

Preserve literal identifiers exactly: Jira keys, URLs, commits, change IDs, branches, versions, environments, config keys, function names, and error codes.

## Fit

Use this skill only when the bug is already fixed or the user supplies the completed fix details.

If the user is asking to diagnose, reproduce, implement, validate live systems, deploy, or update Jira, state that this skill only summarizes already-fixed bugs and stop. Do not switch into those workflows from this skill.

## Jira Inputs

When the user provides only a Jira key or URL, inspect the issue read-only before drafting. Gather the fields and linked evidence needed to prove fixed state and summarize the change: status, resolution, summary, description, comments, fix versions, linked issues, remote links, and changelog only when it clarifies fixed state or validation.

Closed or done status alone does not prove a fix. Proceed only when the resolution or supporting evidence shows a completed fix. If the issue was closed as duplicate, canceled, won't fix, cannot reproduce, superseded, obsolete, or another non-fix outcome, state that this skill summarizes fixed bugs and stop or ask one clarification question if the evidence conflicts.

## Workflow

1. Confirm the fixed state. Proceed when the issue status, resolution, comments, commits, release/build records, or the user's statement show the fix is complete. If fixed state is unclear, ask one bundled clarification question.
2. Gather only supported facts. Extract the symptom, affected users or workflow, business impact, root cause, fixed behavior, fix location, client or deployment requirement, effective fix records, and validation evidence.
3. Classify gaps. If a fact is unavailable, label it as `Not confirmed in the supplied material` or `Not applicable`; do not infer it from adjacent details.
4. Load `references/change-records.md` before writing `Fix Records`. Include only records that prove the effective changed result.
5. Draft for stakeholders. Put user-visible impact and fixed behavior before implementation detail. Keep technical anchors precise but brief.
6. Self-check. Confirm every claim is supported by the supplied material, every identifier is preserved exactly, and validation is labelled as confirmed or suggested.

## Evidence Rules

- Treat Jira summaries, descriptions, comments, linked tickets, commits, builds, deployments, and user-provided context as evidence only for what they explicitly say.
- Prefer the latest authoritative record when old comments conflict with newer resolution notes, commits, deployments, or user instructions.
- Do not claim a customer, environment, platform, release, root cause, test, deployment, or regression result unless the evidence states it.
- If the evidence only says a code change merged, describe the fix record as merged or landed; do not claim it is deployed unless deployment evidence exists.
- Use neutral system wording. Describe faulty conditions and missing handling; do not assign blame to a person or team.

## Output

Use this structure unless the user asks for a different format. Keep it concise enough for a stakeholder update while preserving exact identifiers.

```markdown
## Bugfix Summary

<One short paragraph covering the observed issue, who or what was affected, and the fixed outcome.>

### Impact Scope

<Affected feature, entry point, platform/environment, workflow stage, and confirmed unaffected adjacent flows. Mark unknowns explicitly.>

### Root Cause

<Plain-language cause first. Add technical anchors only when they clarify why the issue happened.>

### Fix

<What changed, where it changed, the new behavior, and whether a client update, release, deployment, config change, or data change is required.>

### Fix Records

<Effective records only, formatted using `references/change-records.md`. If unavailable with approval, say so explicitly.>

### Validation

<Start each item with `Validated:` only for confirmed validation. Use `Suggested validation:` for unrun checks. Include prerequisites, action, expected result, reverse/recovery checks when relevant, and regression scope.>
```

## Rules

- Ask at most one bundled clarification question before drafting. Bundle all missing facts together.
- If the user approves omissions or asks for a best-effort draft, mark missing facts explicitly and continue.
- Prefer short paragraphs and concrete bullets over long incident-report prose.
- Separate confirmed facts from suggested follow-up. Do not hide uncertainty in passive language.
- Keep validation executable: prerequisite, action, expected result, and regression boundary.
- Separate failing paths from already-correct paths when it helps validation.
- Do not list merge requests, reviews, pipeline runs, draft branches, temporary branches, or pending changes as fix records unless they also identify the effective landed change, deployment, config publication, data migration, or build version.
