---
name: jira-bugfix-summarizer
description: "Draft a read-only stakeholder summary or Jira-ready comment for an already fixed Jira bug. Use for impact, root cause, fix records, and validation evidence; not for diagnosis, reproduction, implementation, live validation, deployment, Jira mutation, file writes, or external posting."
---

# Bugfix Summarizer

Create a non-technical stakeholder-facing summary of a fixed bug.

This is read-only. Inspect only authorized Jira issue details, linked resources, supplied diffs, release notes, logs, comments, and commits. Do not create, update, transition, attach to, write to, or submit comments in Jira, repositories, files, or external systems.

Preserve literal identifiers exactly while inspecting evidence. Outside `Fix Records`, apply the Output guardrails.

## Fit

Use this skill only when the bug is already fixed or the user supplies the completed fix details.

If the user is asking to diagnose, reproduce, implement, validate live systems, deploy, update release notes, write files, or mutate Jira or another external system, state that this skill only drafts read-only summaries of already-fixed bugs and stop.

If the user asks to add, post, or comment the summary in Jira, draft Jira-ready text, apply Jira-ready formatting from Output, and stop before the external mutation.

## Jira Inputs

When the user provides only a Jira key or URL, inspect the issue read-only before drafting. Treat Jira status as context, not proof of a fix. Gather only the fields and linked evidence needed to prove fixed state and summarize the change: current status, resolution, summary, description, comments, fix versions, linked issues, remote links, and changelog only when it clarifies fixed state or validation.

Proceed only when the resolution or supporting evidence shows a completed fix. Treat a current non-terminal status such as open, reopened, or in progress as conflicting evidence unless newer resolution notes, commits, release/build records, or the user's statement clearly show the fix is complete. If the issue was closed as duplicate, canceled, won't fix, cannot reproduce, superseded, obsolete, or another non-fix outcome, state that this skill summarizes fixed bugs and stop or ask one clarification question if the evidence conflicts.

## Workflow

1. Confirm the fixed state as defined in Jira Inputs. If current Jira status conflicts with the fix evidence, or fixed state is otherwise unclear, ask one bundled clarification question.
2. Gather only supported facts. Extract the symptom, affected users or workflow, business impact, plain-language root cause, fixed behavior, user-required action, validation evidence, and inputs needed for `Fix Records`.
3. Classify gaps. If a fact is unavailable, label it as `Not confirmed in the supplied material` or `Not applicable`; do not infer it from adjacent details.
4. Load `references/fix-records.md` before drafting the default `Fix Records` section.
5. Draft using the Output structure, putting user-visible impact, fixed behavior, required action, and validation before traceability detail.
6. If the user asked for Jira placement, apply Jira-ready formatting from Output before responding.
7. Self-check. Confirm every claim is supported by the supplied material, non-`Fix Records` sections omit Jira metadata and internal deployment details, `Fix Records` satisfies `references/fix-records.md`, validation is labelled as confirmed or suggested, and Jira-ready output satisfies the Jira-ready formatting rule.

## Evidence Rules

- Treat Jira summaries, descriptions, comments, linked tickets, commits, builds, deployments, and user-provided context as evidence only for what they explicitly say.
- Prefer the latest authoritative record when old comments conflict with newer resolution notes, commits, deployments, or user instructions.
- Do not claim a customer, environment, platform, release, root cause, test, deployment, or regression result unless the evidence states it.
- Use deployment, release, build, and publication records as evidence that the fix is complete.
- Use neutral system wording. Describe faulty conditions and missing handling; do not assign blame to a person or team.

## Output

Use this structure unless the user asks for a different format. Keep it concise enough for a non-technical stakeholder update.

Final-summary guardrails: omit all Jira metadata (issue ID, URL, status, resolution, field names, transitions, internal ticket workflow) and all internal deployment, release, build, branch, environment, or publication details (including rollout timing and landed/merged wording). Include customer-facing version, release, configuration, data, or update identifiers only when they are required for user action, validation, or disambiguation. These guardrails govern the main summary except the separate traceability details in `Fix Records`, where linked modification records and necessary source-control, build, deployment, configuration, data, or migration identifiers are allowed.

Format each section as scannable Markdown. Use one short paragraph for a single idea; when a section has multiple distinct facts, actions, records, or validation methods, split them into unordered bullets or separate unnumbered paragraphs instead of one dense paragraph or a numbered sequence. In `Validation`, each distinct method or check is its own bullet, starting with `Validated:` for confirmed checks or `Suggested validation:` for unrun checks.

Jira-ready formatting: for Jira placement requests, preserve the drafted Markdown as the exact body handed to any later authorized Jira workflow. Keep heading levels, paragraph breaks, unordered bullets, and Markdown links. If a Jira tool requires structured rich text instead of Markdown, map the draft to equivalent heading, paragraph, bullet, and link blocks rather than collapsed plain text.

```markdown
## Bugfix Summary

<One short paragraph covering the observed issue, who or what was affected, and the fixed outcome. Avoid implementation detail here.>

### Impact Scope

<Affected feature or workflow, user-visible scope, platform/environment only when relevant, and confirmed unaffected adjacent flows. Mark unknowns explicitly.>

### Root Cause

<Plain-language cause.>

### Fix Records

<Fix explanation and modification records. Follow `references/fix-records.md`.>

### Validation

- `Validated:` <Confirmed check with prerequisite, action, expected result, reverse/recovery checks when relevant, and regression scope.>
- `Suggested validation:` <Unrun check with prerequisite, action, expected result, reverse/recovery checks when relevant, and regression scope.>
```

## Rules

- Ask at most one bundled clarification question before drafting. Bundle all missing facts together.
- If the user approves omissions or asks for a best-effort draft, mark missing facts explicitly and continue.
- Write for non-technical readers. Omit implementation internals, stack traces, file paths, function names, config keys, and low-level code details unless the user requested them or they are needed to understand impact, required action, validation, or traceability.
- Separate confirmed facts from suggested follow-up. Do not hide uncertainty in passive language.
- Keep validation executable: prerequisite, action, expected result, and regression boundary.
- Separate failing paths from already-correct paths when it helps validation.
