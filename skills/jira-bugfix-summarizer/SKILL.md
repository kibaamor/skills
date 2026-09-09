---
name: jira-bugfix-summarizer
description: Summarize an already diagnosed and fixed Jira issue for non-technical readers, covering user impact, root cause, fix behavior, effective fix records, and validation suggestions.
---

# Bugfix Summarizer

Use this skill when the user asks for a summary of an already fixed Jira issue. Generate only the summary text; do not submit, comment on, or write to Jira or any external system.

The target audience is non-technical stakeholders, and the final summary must be in Chinese. Explain the user-visible impact and process-level cause first, then add only the necessary technical anchors, fixed behavior, effective fix records, and suggested validation.

## Workflow

1. Gather enough facts to cover the information checklist below.
2. When key information is missing or cannot be confirmed, ask the user first; if the user explicitly cannot provide it, briefly note the limitation in the summary.
3. Use the default structure unless the user requests another format.
4. Before finishing, check that the summary uses functional process language, neutral non-blaming wording, proper Markdown paragraph spacing, clearly states any client update requirement, and includes clickable links to the effective fix records.

## Information Checklist

- Issue context: Jira key, title, current status, and user-visible symptom.
- Impact scope: affected feature, entry point, platform or environment, and workflow stage; when needed, mention adjacent flows that were not affected.
- Root cause: the process decision, state transfer, or data publication step where the issue occurred; use technical terms only as anchors.
- Fix behavior: the behavior after the fix, and whether the fix is server-only, client-only, config-only, data-only, or requires a new client build.
- Fix records: authoritative records and URLs showing the effective changed result; do not list records that only describe submission, review, merge, or build process.
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

- `<Source/system> <branch/environment>`：[`<display ID>`](<URL showing the effective changed result>) - `<functional change description in Chinese>`

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

When generating `修复记录`, read [references/change-records.md](references/change-records.md). Omit record types that do not exist; keep only entries that show the effective changed result.

## Writing Constraints

- Use Markdown paragraph format correctly: separate headings, paragraphs, lists, and fix-record bullets with blank lines; do not collapse unrelated ideas into one paragraph.
- Use heading levels to make the final summary readable: `##` for the overall summary title, `###` for major sections, and `####` for validation subsections.
- Prefer prose paragraphs for summary, impact, root cause, and fix content. Use bullets only for fix records, and use short ordered lists inside validation subsections only when the user needs exact step order.
- Use functional process language and minimize code-level wording; explain unavoidable technical terms by their user-visible meaning the first time they appear.
- Keep only technical details that support the judgment, such as API names, error codes, config names, version numbers, service names, or data tables.
- Make boundaries explicit, such as pre-check vs final submit, draft vs publish, client vs server, or source branch vs target branch.
- When the distinction helps validation, describe the failing path separately from paths that already behaved correctly.
- Write validation suggestions as executable steps: action plus expected result; when relevant, include recovery, reverse cases, and regression checks.
- Use neutral, non-blaming wording focused on systems, processes, and information gaps. Examples: `流程缺少状态校验`, `配置发布前缺少自动校验`, `该场景未被现有回归用例覆盖`, `系统没有阻止重复提交`.
