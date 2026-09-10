---
name: jira-bugfix-summarizer
description: Summarize already fixed Jira issues for non-technical stakeholders; use when the user needs impact, root cause, fix behavior, effective fix records, client-update requirements, and validation suggestions, not for active bug diagnosis or Jira/resource updates.
---

# Bugfix Summarizer

Produce a stakeholder-facing summary for an already fixed Jira bug. Generate only the summary text.

Do not create, update, edit, submit, comment on, or write to Jira, external systems, files, repositories, or any other resource. If the user asks to modify a resource, state that this skill only summarizes already fixed issues and stop.

Preserve literal technical identifiers verbatim, including Jira keys, commit IDs, change IDs, URLs, versions, branches, function names, error codes, environment names, and config keys. Explain user-visible impact and process-level cause before technical detail.

## Workflow

1. Confirm the task fits: the issue is already fixed and the user wants a summary, not diagnosis, implementation, or Jira updates. Completion: the available facts include fixed status or the user confirms it.
2. Collect the minimum facts needed for the checklist below. Completion: each checklist item is either known or explicitly unavailable with user approval to continue.
3. If fix records will be included, read `references/change-records.md` before drafting. Completion: every listed record is an effective changed result under those rules, or the user has approved continuing without one.
4. Draft the summary using the default structure unless the user requests another layout. Completion: the output covers impact, root cause, fixed behavior, fix records, client-update requirements, and validation.
5. Self-check before responding. Completion: the final answer contains no unsupported facts and does not imply validation passed unless confirmed.

## Information Checklist

- Fixed status: evidence or confirmation that the Jira issue is already fixed. If missing, ask for confirmation before continuing. If the user cannot confirm the fix, state that this skill only summarizes already fixed issues and stop.
- User-visible symptom: what users observed, not just the Jira title or internal status.
- Impact scope: affected feature, entry point, platform or environment, workflow stage, and any adjacent flows confirmed not affected.
- Root cause: the process decision, state transfer, data publication step, config gap, or state validation gap where the issue occurred.
- Fixed behavior: what changed, which layer changed, and whether the fix is server-only, client-only, config-only, data-only, or requires a new client build.
- Fix records: effective records and URLs that prove where the changed result landed; apply `references/change-records.md` before listing them.
- Validation suggestions: prerequisites, execution steps, expected results, and relevant reverse, recovery, or regression checks.

Do not present unconfirmed logs, test results, deployment status, or validation status as facts. In the validation section, start with `Validated:` only when validation has been confirmed; otherwise start with `Suggested validation:`.

## Default Output

```markdown
## Bugfix Summary

<One short paragraph describing the observed issue and the fixed outcome.>

### Impact Scope

<One paragraph describing the affected feature, entry point, platform or environment, and workflow stage.>

<When useful, add a second short paragraph describing adjacent flows that were not affected. Omit this paragraph if it adds no value.>

### Root Cause

<One paragraph explaining the root cause in business process terms.>

<If technical anchors are necessary, add a separate short paragraph with function names, error codes, request or message types, config keys, service names, or data tables. Omit this paragraph if there are no useful anchors.>

### Fix

<One paragraph describing what changed, where it changed, and the new behavior.>

<One paragraph clearly stating whether a client update or new client build is required. If no client update is required, state that explicitly.>

### Fix Records

<Write fix records using the selection, format, and no-record fallback in `references/change-records.md`.>

### Validation

<Start with either `Validated:` or `Suggested validation:` based on the confirmation rule above.>

#### 1. Prerequisites

<State the required account, data, config, environment, client version, or server version.>

#### 2. Steps

<State the exact client-side or server-side steps. Use a short numbered list only when multiple actions must be performed in order.>

#### 3. Expected Result

<State the expected visible behavior, returned state, or published data result.>

#### 4. Reverse Or Recovery Checks

<State the reverse case, blocked path, recovery path, or unblock check when relevant. Omit this subsection if it does not apply.>

#### 5. Regression Scope

<State the related flows that should still work.>
```

## Writing Constraints

- Use Markdown paragraph format correctly: separate headings, paragraphs, lists, and fix-record bullets with blank lines; do not collapse unrelated ideas into one paragraph.
- Use heading levels to make the final summary readable: `##` for the overall summary title, `###` for major sections, and `####` for validation subsections.
- Prefer paragraphs for summary, impact, root cause, and fix content. Use bullets only for fix records, and use short ordered lists inside validation subsections only when the user needs exact step order.
- Minimize code-level wording; explain unavoidable technical terms by their user-visible meaning the first time they appear.
- Include only supplied technical identifiers that materially disambiguate or support the impact, root cause, fix, record, or validation. Keep root-cause identifiers in the dedicated root-cause anchor paragraph; place versions, fix-record IDs, configuration prerequisites, and other execution-critical identifiers in their owning sections.
- Make boundaries explicit, such as pre-check vs final submit, draft vs publish, client vs server, or source branch vs target branch.
- When the distinction helps validation, describe the failing path separately from paths that already behaved correctly.
- Write validation suggestions as executable steps: action plus expected result; when relevant, include recovery, reverse cases, and regression checks.
- Use neutral, non-blaming wording focused on systems, processes, and information gaps. Examples: `the flow did not validate the state transition`, `the publication process did not include an automated config check`, `the existing regression suite did not cover this scenario`, `the system did not block duplicate submission`.
