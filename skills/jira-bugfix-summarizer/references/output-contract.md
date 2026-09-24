# Output Contract

Use the user's requested language. Unless another format is requested, use these sections in order.

## Bugfix Summary

One short paragraph: observed problem when known, affected workflow or audience, and fixed outcome. If the pre-fix symptom is unknown, say so and describe only the supported workflow and fixed outcome. State required user action or a confirmed absence of action when it materially affects use of the fix.

## Impact Scope

One paragraph or compact bullets: confirmed affected scope, material unaffected scope, and only material unknown scope.

## Root Cause

One plain-language paragraph describing the faulty condition or missing handling without personal blame. If no cause is supported, state that it is not confirmed.

## Fix Records

One short paragraph describing the functional change and material user action, followed by the records selected under `fix-records.md` or its exact fallback sentence.

## Validation

Choose Validation content from the evidence:

- For each completed check, give a `Validated:` bullet with the supported prerequisite, action, and observed result.
- Give a bullet starting exactly `Suggested validation:` for a supplied unrun plan with an action and expected result, a concrete untested failure mode in the evidence, or an explicit user request for validation guidance. For a user-requested check, derive the action and expected result from the supported workflow and fixed behavior. Label every proposed check unrun and omit unsupported dimensions.
- If evidence only names a check that was not run, state that material unrun boundary in a sentence.
- If neither kind of check is established, state concisely that no completed validation result was supplied.

Include reverse, recovery, rollback, platform, and regression boundaries only when evidence supplies them. Unknown impact alone does not justify inventing a test. Never present a suggested check as completed.

## Information placement

Every stakeholder-facing section omits Jira key, URL, status, resolution, fields, transitions, and internal branch, merge, build, deployment, publication, environment, and rollout details. The traceability entries inside `Fix Records` are the exception. Customer-facing versions, configuration, data, or migration identifiers may appear elsewhere only for user action, validation, or disambiguation.

Keep sections scannable: one paragraph for one idea; bullets for multiple facts or checks. Preserve supplied literal identifiers inside traceability details.

## Jira-ready requests

Give one short capability statement only when necessary, then the exact draft body. The body does not mention the skill, policy, unavailable tool mechanics, or an unperformed mutation. Preserve Markdown headings, paragraphs, bullets, and links. A later authorized rich-text workflow maps those blocks without flattening them.

## Example

```markdown
## Bugfix Summary

Retrying iOS checkout after a payment timeout could show a second pending authorization. The published fix makes the retry reuse the original payment request.

### Impact Scope

The confirmed scope is the iOS timeout-retry flow. Customer count and impact on other clients are not confirmed.

### Root Cause

The retry did not retain the identifier that marks repeated payment attempts as the same request.

### Fix Records

The retry now retains that identifier through a timeout.

- `iOS release`: [`9.14.2`](https://releases.example.com/mobile/ios-9.14.2) - Published the corrected retry behavior.

### Validation

- `Validated:` A simulated timeout followed by a retry produced one authorization.
```

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Treating Jira status as proof | Apply the fixed-state evidence table |
| Listing a release and its subsumed commit | Keep the most downstream effective record |
| Printing every absent fact | Surface only material unknowns |
| Inventing regression or platform checks | Include supported or materially necessary checks only |
| Explaining skill or tool mechanics in the draft | Give only a necessary capability statement outside the body |
