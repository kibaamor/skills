---
name: jira-bugfix-summarizer
description: Summarize already fixed Jira issues in Chinese for non-technical stakeholders; use for impact, root cause, client-update needs, effective fix records, and validation suggestions, not for Jira comments, updates, or any resource changes.
---

# Bugfix Summarizer

Use this skill when the user asks for a summary of an already fixed Jira issue. Generate only the summary text; do not create, update, edit, submit, comment on, or write to Jira, external systems, files, repositories, or any other resource. If the user asks to modify any resource, explain in Chinese that this skill only summarizes already fixed issues and stop.

The target audience is non-technical stakeholders, and the final summary must be in Chinese. Write all prose in Chinese, translating non-Chinese descriptive text by meaning; preserve literal technical identifiers verbatim, such as keys, IDs, function names, URLs, versions, branches, and environment names. Explain the user-visible impact and process-level cause before technical detail, then cover the fixed behavior, effective fix records, and suggested validation.

## Workflow

1. Treat information supplied by the user or referenced records as facts unless explicit contrary evidence is available. If facts conflict, ask the user to resolve the conflict. Do not add unsupported facts.
2. Before generating the summary, obtain enough facts to cover the checklist: confirmation that the issue is already fixed, user-visible symptom, impact scope, root-cause process step, changed behavior and affected layer, whether a client update or new build is required, and fix-record evidence or explicit agreement to continue without an effective record. Ask for any missing item and wait for the reply.
3. For fix-record selection and the missing-record fallback, read [references/change-records.md](references/change-records.md) before generating the final summary.
4. Use the default structure unless the user requests another layout. A custom layout must still cover impact, root cause, fix behavior, fix records, client update requirements, and validation.

## Information Checklist

- Issue context: use the Jira key, title, and status only to identify the issue and confirm that it is already fixed; describe the user-visible symptom rather than the Jira record or status. If fixed status is missing, ask the user to confirm that the issue is already fixed before continuing. If explicit evidence indicates that the issue is not fixed or the supplied facts conflict about whether it is fixed, ask the user to confirm the fix before continuing. If the user cannot or will not confirm that the issue is fixed, explain in Chinese that this skill only summarizes already fixed issues and stop.
- Impact scope: affected feature, entry point, platform or environment, and workflow stage; when needed, mention adjacent flows that were not affected.
- Root cause: the process decision, state transfer, or data publication step where the issue occurred; use technical terms only as anchors.
- Fix behavior: the behavior after the fix, and whether the fix is server-only, client-only, config-only, data-only, or requires a new client build.
- Fix records: records and URLs offered as evidence for the changed result; apply the fix-record reference rules before listing them.
- Validation suggestions: prerequisites, steps, expected results, and reverse cases, recovery flows, or regression scenarios that should be covered.

Do not present unconfirmed logs, test results, or validation status as facts. Write `已验证通过` only when it has actually been confirmed; otherwise write `建议验证`.

## Default Output

```markdown
## 问题与修复总结

<Write one short Chinese paragraph describing the observed issue and the fixed outcome. Keep it as prose, not a list.>

### 影响范围

<Write one Chinese paragraph describing the affected feature, entry point, platform or environment, and workflow stage.>

<When useful, add a second short Chinese paragraph describing adjacent flows that were not affected. Omit this paragraph if it adds no value.>

### 根本原因

<Write one Chinese paragraph explaining the root cause in business process language.>

<If technical anchors are necessary, add them in a separate short Chinese paragraph, such as function names, error codes, request or message types, config keys, service names, or data tables. Omit this paragraph if there are no useful anchors.>

### 修复内容

<Write one Chinese paragraph describing what changed, where it changed, and the new behavior.>

<Write one Chinese paragraph clearly stating whether a client update or new client build is required. If no client update is required, state that explicitly.>

### 修复记录

<Write fix records using the selection, format, and no-record fallback in references/change-records.md.>

### 验证建议

#### 1. 准备条件

<State the required account, data, config, environment, client version, or server version in Chinese.>

#### 2. 操作路径

<State the exact client-side or server-side steps in Chinese. Use a short numbered list only when multiple actions must be performed in order.>

#### 3. 预期结果

<State the expected visible behavior, returned state, or published data result in Chinese.>

#### 4. 反向检查

<State the reverse case, blocked path, recovery path, or unblock check in Chinese when relevant. Omit this subsection if it does not apply.>

#### 5. 回归范围

<State the related flows that should still work in Chinese.>
```

## Writing Constraints

- Use Markdown paragraph format correctly: separate headings, paragraphs, lists, and fix-record bullets with blank lines; do not collapse unrelated ideas into one paragraph.
- Use heading levels to make the final summary readable: `##` for the overall summary title, `###` for major sections, and `####` for validation subsections.
- Prefer prose paragraphs for summary, impact, root cause, and fix content. Use bullets only for fix records, and use short ordered lists inside validation subsections only when the user needs exact step order.
- Use functional process language and minimize code-level wording; explain unavoidable technical terms by their user-visible meaning the first time they appear.
- Include only supplied technical identifiers that materially disambiguate or support the impact, root cause, fix, record, or validation. Keep root-cause identifiers in the dedicated root-cause anchor paragraph; place versions, fix-record IDs, configuration prerequisites, and other execution-critical identifiers in their owning sections.
- Make boundaries explicit, such as pre-check vs final submit, draft vs publish, client vs server, or source branch vs target branch.
- When the distinction helps validation, describe the failing path separately from paths that already behaved correctly.
- Write validation suggestions as executable steps: action plus expected result; when relevant, include recovery, reverse cases, and regression checks.
- Use neutral, non-blaming wording focused on systems, processes, and information gaps. Examples: `流程缺少状态校验`, `配置发布前缺少自动校验`, `该场景未被现有回归用例覆盖`, `系统没有阻止重复提交`.
