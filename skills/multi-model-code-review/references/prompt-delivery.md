# Prompt Rendering and Delivery Audit

## Required rule

The child receives the rendered role template—not a summary, path-only instruction, or a flattened paraphrase. The exact prompt argument validated before dispatch must be the exact string passed to the host's child-prompt parameter.

## Render

Each role template has explicit uppercase placeholders. Create a UTF-8 JSON values file, then render it:

```bash
python scripts/render_prompt.py \
  --template prompts/discovery-reviewer.md \
  --values audit/D1.values.json \
  --output audit/D1.rendered-prompt.txt
```

Use the analogous Verification template and values for V1. Rendering is literal replacement. Do not run another summarization or formatting pass on the result.

## Capture the actual child prompt argument

Save the exact string assigned to the actual child-dispatch prompt argument as `prompt_argument_path`. Acceptable capture methods:

- `dispatch_argument_capture`: copied from the actual serialized child-dispatch call/tool trace;
- `exact_argument_variable`: the same immutable string variable is saved and passed directly as the child prompt argument, with no intervening transformation.

A separately regenerated prompt that was not tied to the actual dispatch argument is not evidence of what the child received. If neither capture method is possible, prompt delivery is unverified.

## Individual validation

```bash
python scripts/validate_prompt.py \
  --role discovery \
  --template prompts/discovery-reviewer.md \
  --values audit/D1.values.json \
  --actual-prompt audit/D1.prompt-argument.txt \
  --report audit/D1.prompt-validation.json
```

The validator:

- re-renders the expected prompt using the template and values;
- checks the role-to-template mapping;
- checks required headings and their order;
- rejects unresolved placeholders and missing output sections;
- compares the actual prompt argument to the expected rendered text exactly, including Markdown, whitespace, line endings, and final newline;
- reports expected/actual SHA-256 and the first differing line.

## Batch dispatch audit manifest

After dispatch, create a JSON manifest in the audit directory. All relative paths are resolved from the manifest's directory.

```json
{
  "expected_discovery_reviewers": ["D1", "D2"],
  "verification_expected": true,
  "dispatches": [
    {
      "reviewer_id": "D1",
      "role": "discovery",
      "model_route": "model-a",
      "dispatch_id": "host-child-id-1",
      "capture_method": "dispatch_argument_capture",
      "fresh_context_evidence": "Host returned a distinct child session identifier",
      "template_path": "../prompts/discovery-reviewer.md",
      "values_path": "D1.values.json",
      "prompt_argument_path": "D1.prompt-argument.txt"
    },
    {
      "reviewer_id": "D2",
      "role": "discovery",
      "model_route": "model-b",
      "dispatch_id": "host-child-id-2",
      "capture_method": "exact_argument_variable",
      "fresh_context_evidence": "A new child execution context was created",
      "template_path": "../prompts/discovery-reviewer.md",
      "values_path": "D2.values.json",
      "prompt_argument_path": "D2.prompt-argument.txt"
    },
    {
      "reviewer_id": "V1",
      "role": "verification",
      "model_route": "parent-session-model",
      "dispatch_id": "host-child-id-3",
      "capture_method": "dispatch_argument_capture",
      "fresh_context_evidence": "A separate child context was created for Verification",
      "template_path": "../prompts/verification-reviewer.md",
      "values_path": "V1.values.json",
      "prompt_argument_path": "V1.prompt-argument.txt"
    }
  ]
}
```

For a no-candidate run, set `verification_expected` to `false` and omit V1. For a run with candidates, set it to `true` and include exactly one Verification record.

Run the batch audit:

```bash
python scripts/validate_dispatch_prompts.py \
  --manifest audit/dispatch-audit.json \
  --report audit/dispatch-prompt-validation.json
```

The script verifies every expected Discovery Reviewer, Verification expectation, unique reviewer/dispatch IDs, model-route presence, capture provenance, fresh-context evidence, role/template mapping, and exact rendered prompt match.

## Failure handling

Any mismatch means the Reviewer did not receive a proven template-conformant prompt. Do not repair the audit record by replacing the captured prompt with the expected prompt. Correct the dispatch and create a new child context if the host permits. Otherwise mark prompt delivery unverified and the overall review PARTIAL.
