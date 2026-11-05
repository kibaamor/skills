# Evaluation Suite

`evals.json` defines 45 behavioral acceptance tests. Some are locally executable validator tests; others are runtime integration tests that require a real host dispatch and project fixture.

## Required local command

Run from the Skill root:

```bash
python scripts/self_test.py
```

This exercises both positive and negative cases for prompt rendering, prompt-template matching, actual dispatch-prompt auditing, Discovery schema validation, Verification schema validation, duplicate JSON keys, and candidate coverage.

## Required integration evidence

For each actual Discovery and Verification dispatch, save:

- exact role template path and template hash;
- exact values used to render the prompt;
- exact prompt argument captured from the child-dispatch call (or the exact immutable argument variable passed to that call);
- model route, reviewer ID, dispatch ID, and fresh-context evidence;
- prompt audit result.

Create a dispatch manifest and run:

```bash
python scripts/validate_dispatch_prompts.py --manifest <dispatch-audit.json>
```

The audit compares every actual prompt argument byte-for-byte with the prompt rendered from the corresponding template and values. It rejects wrong role/template mappings, missing reviewers, missing captures, flattened/truncated prompts, unresolved placeholders, and content differences. A separately generated prompt that was not tied to the actual dispatch argument is not proof of what the child received.

## Required output validation

Save each raw response exactly as returned by the Reviewer. Validate Discovery:

```bash
python scripts/validate_review_output.py \
  --role discovery \
  --schema schemas/discovery-result.schema.json \
  --input <raw-discovery-response.json>
```

Validate Verification with the Controller's expected candidate inventory:

```bash
python scripts/validate_review_output.py \
  --role verification \
  --schema schemas/verification-result.schema.json \
  --input <raw-verification-response.json> \
  --expected-candidates <expected-candidates.json>
```

The expected-candidates file has this shape:

```json
{
  "findings": ["C-F-001", "C-F-002"],
  "recommendations": ["C-R-001"]
}
```

The output validator is self-contained and uses the constrained JSON Schema keywords used by the bundled schemas. It also checks duplicate JSON keys, semantic constraints, and exact candidate ID coverage.

## Pass criteria

A final report claiming a prompt was template-compliant must be backed by `validate_dispatch_prompts.py` output. A report claiming reviewer JSON was valid must be backed by `validate_review_output.py` output for every raw response. Evals that require actual child dispatch cannot be considered passed from local template inspection alone.
