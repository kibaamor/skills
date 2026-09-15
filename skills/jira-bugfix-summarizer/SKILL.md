---
name: jira-bugfix-summarizer
description: "Use when asked to summarize an already fixed Jira bug for stakeholders, including impact, root cause, fix, and validation. Do not use for diagnosing unresolved bugs, implementing fixes, or updating Jira."
---

# Bugfix Summarizer

Create a non-technical stakeholder-facing summary of a bug after the fix is already known.

This is a read-only summarization skill. You may read Jira issue details, linked resources, supplied diffs, release notes, logs, comments, and commits that the user authorized you to inspect. Do not create, update, transition, comment on, attach to, or write to Jira, repositories, files, or external systems.

Preserve literal identifiers exactly while inspecting evidence. In the final stakeholder summary, do not mention Jira IDs, Jira URLs, Jira field names, Jira status, or Jira resolution. Include other identifiers only when they are essential for user action, validation, or disambiguation.

## Fit

Use this skill only when the bug is already fixed or the user supplies the completed fix details.

If the user is asking to diagnose, reproduce, implement, validate live systems, deploy, or update Jira, state that this skill only summarizes already-fixed bugs and stop. Do not switch into those workflows from this skill.

## Jira Inputs

When the user provides only a Jira key or URL, inspect the issue read-only before drafting. Treat Jira status as context, not proof of a fix. Gather only the fields and linked evidence needed to prove fixed state and summarize the change: current status, resolution, summary, description, comments, fix versions, linked issues, remote links, and changelog only when it clarifies fixed state or validation.

Jira status alone does not prove a fix. Proceed only when the resolution or supporting evidence shows a completed fix. Treat a current non-terminal status such as open, reopened, or in progress as conflicting evidence unless newer resolution notes, commits, release/build records, or the user's statement clearly show the fix is complete. If the issue was closed as duplicate, canceled, won't fix, cannot reproduce, superseded, obsolete, or another non-fix outcome, state that this skill summarizes fixed bugs and stop or ask one clarification question if the evidence conflicts.

## Workflow

1. Confirm the fixed state without treating Jira status as proof. Proceed when the resolution, comments, commits, release/build records, or the user's statement show the fix is complete. If current Jira status conflicts with those records, or fixed state is otherwise unclear, ask one bundled clarification question.
2. Gather only supported facts. Extract the symptom, affected users or workflow, business impact, plain-language root cause, fixed behavior, user-required action, effective fix records for internal traceability, and validation evidence.
3. Classify gaps. If a fact is unavailable, label it as `Not confirmed in the supplied material` or `Not applicable`; do not infer it from adjacent details.
4. Load `references/change-records.md` only if the user explicitly asks for a fix-records appendix. Keep those records out of the default stakeholder summary.
5. Draft for non-technical stakeholders. Put user-visible impact, fixed behavior, required action, and validation before implementation detail. Keep technical anchors only when they are necessary to identify the fix, explain customer impact, or support validation.
6. Self-check. Confirm every claim is supported by the supplied material, the final summary omits Jira metadata and internal deployment details, and validation is labelled as confirmed or suggested.

## Evidence Rules

- Treat Jira summaries, descriptions, comments, linked tickets, commits, builds, deployments, and user-provided context as evidence only for what they explicitly say.
- Prefer the latest authoritative record when old comments conflict with newer resolution notes, commits, deployments, or user instructions.
- Do not claim a customer, environment, platform, release, root cause, test, deployment, or regression result unless the evidence states it.
- Use deployment, release, build, and publication records as evidence that the fix is complete. Do not mention internal deployment details in the final stakeholder summary unless the user explicitly asks for a traceability appendix. Include customer-facing version, configuration, data, or update identifiers only when they are required for user action, validation, or disambiguation.
- Use neutral system wording. Describe faulty conditions and missing handling; do not assign blame to a person or team.

## Output

Use this structure unless the user asks for a different format. Keep it concise enough for a non-technical stakeholder update. Do not include Jira metadata or internal deployment, release, build, branch, environment, or publication details in the summary. Customer-facing version, configuration, data, or update identifiers are allowed when they are required for user action, validation, or disambiguation.

```markdown
## Bugfix Summary

<One short paragraph covering the observed issue, who or what was affected, and the fixed outcome. Avoid implementation detail here.>

### Impact Scope

<Affected feature or workflow, user-visible scope, platform/environment only when relevant, and confirmed unaffected adjacent flows. Mark unknowns explicitly.>

### Root Cause

<Plain-language cause. Add technical anchors only when they are needed to explain the impact or prevent ambiguity.>

### Fix

<What changed in user-facing terms, the new behavior, and any action the user or customer must take. Do not mention internal deployment, release, build, branch, environment, or publication details. Include customer-facing version, configuration, data, or update identifiers only when needed for action, validation, or disambiguation. Include low-level locations only when they are essential.>

### Validation

<Start each item with `Validated:` only for confirmed validation. Use `Suggested validation:` for unrun checks. Include prerequisites, action, expected result, reverse/recovery checks when relevant, and regression scope.>
```

## Rules

- Ask at most one bundled clarification question before drafting. Bundle all missing facts together.
- If the user approves omissions or asks for a best-effort draft, mark missing facts explicitly and continue.
- Prefer short paragraphs and concrete bullets over long incident-report prose.
- Write for non-technical readers. Include technical details only when they are needed to understand impact, required action, validation, or traceability.
- Omit implementation internals, stack traces, file paths, function names, config keys, and low-level code details unless the user requested them or they are essential evidence.
- Treat Jira status as context, not evidence of fixed state. If current status conflicts with fix evidence, resolve the conflict before drafting. Do not mention Jira status in the final summary.
- Omit Jira metadata from the final summary, including Jira ID, Jira URL, issue status, resolution, field names, transitions, and internal ticket workflow.
- Omit internal fix deployment details from the final summary, including deployment status, build version, branch, environment, publication record, rollout timing, and landed/merged wording. Include customer-facing release or update identifiers only when they are required for user action, validation, or disambiguation.
- Separate confirmed facts from suggested follow-up. Do not hide uncertainty in passive language.
- Keep validation executable: prerequisite, action, expected result, and regression boundary.
- Separate failing paths from already-correct paths when it helps validation.
- If the user explicitly asks for a separate fix-records appendix, load `references/change-records.md` and include only final effective records; keep the main stakeholder summary free of Jira and deployment details.
