---
name: multi-model-code-review
description: Coordinates independent model-based code reviews with domain-specific engineering analysis, executable validation, and separate adversarial verification. Identifies real defects, assesses engineering quality, and recommends worthwhile improvements through an evidence-backed, actionable report.
---

# Multi-Model Code Review

## Objective

Conduct collaborative code reviews through multiple independent models. Apply relevant software-engineering and domain expertise, run appropriate safe checks, independently verify proposed findings and recommendations, and produce a trustworthy evidence-backed report.

The Skill reviews changes; it does not implement fixes, refactor the project, or perform unrelated repository maintenance.

## Roles

- **Controller:** resolves the review target, prepares shared input, dispatches independent reviewers, manages validation, validates outputs mechanically, consolidates candidates, dispatches Verification, adjudicates, and reports.
- **Discovery Reviewer:** one fresh context for each requested model. Each independently reviews the same logical change set, uses relevant tests/tools where useful, and returns findings and recommendations. Discovery outputs are not shared between reviewers.
- **Verification Reviewer:** one additional fresh context using the parent session's model when it can be selected. It independently investigates every consolidated candidate and returns one verdict per candidate. It does not repeat broad discovery.

A fresh conversation context does not imply an isolated filesystem or worktree. Do not claim filesystem isolation unless the host guarantees it. Reviewers must preserve the project and VCS state even when running checks.

## Workflow

### 1. Resolve the target and baseline

Resolve the requested target from supplied diffs/content, the active VCS, explicit files, or directories. Do not assume a particular VCS or require a VCS snapshot/fingerprint.

For a change review, prepare a **baseline change package** containing:

- the baseline reference or source of comparison, when available;
- the complete change diff, including staged and unstaged changes and relevant untracked files according to the VCS;
- changed-file inventory and status (added, modified, deleted, renamed, untracked);
- current file content or accessible paths for surrounding context;
- relevant requirements, specifications, contracts, project guidance, tests, and architecture facts;
- excluded/inaccessible files and known limitations.

The diff is the primary evidence of what changed. Reviewers must inspect it, not only current files. They may inspect current code and baseline content to understand context and attribute behavior. For untracked files, include their content because ordinary diffs may omit it. Without a reliable baseline/diff, review may continue, but introduction attribution must be `unknown` and the limitation must be reported.

Build the package once and provide every Discovery Reviewer the same logical change set and context. Do not claim byte-identical data unless guaranteed. Expand beyond changed files only to answer a concrete technical question; record why.

Read `references/review-input.md` during this phase.

### 2. Build task-specific engineering context

Prepare concise shared context containing:

- binding requirements, invariants, API/protocol contracts, and non-goals;
- verified languages, runtimes, frameworks, dependencies, protocols, and versions;
- relevant architecture, ownership, lifecycle, and data/control-flow facts;
- concrete risk checks that follow from the actual change.

Convert domain knowledge into checks. For example, do not merely say “understand HTTP/2”; identify the stream states, trailer rules, body completion/error paths, and framing behavior relevant to the changed code. Mark unknowns. Do not invent requirements or infer technology semantics from filenames alone.

Load `references/domain-review-guidance.md` only for the areas relevant to the change.

### 3. Confirm dispatch capability

Use the active host's documented native capabilities to create a genuinely fresh child context per reviewer, select the exact requested model route, pass a complete prompt, and collect the raw response and terminal status. Do not assume a host-specific Task API, agent type, permission syntax, or model-routing field. Do not substitute unavailable models.

Parallel execution is preferred where it is safe; sequential execution is acceptable if each reviewer receives a fresh context. If fresh contexts or per-reviewer model selection are unavailable, disclose that limitation and do not simulate independent review in one context.

### 4. Render, audit, and dispatch Discovery prompts

Read `prompts/discovery-reviewer.md` in full and `references/prompt-delivery.md`. Read `references/validation-execution.md` to provide the validation boundary. Render all template fields using `scripts/render_prompt.py`. Preserve Markdown structure and newlines. Do not abbreviate, summarize, flatten, reorder, or append arbitrary process text to the rendered task prompt.

Before dispatch, render and validate the exact task-prompt value. For each Reviewer:

1. Save the values used for rendering as a JSON file.
2. Render the role template to a UTF-8 file with `scripts/render_prompt.py`.
3. Bind that exact rendered string to the host's child-prompt argument; do not summarize, reformat, concatenate, or append instructions afterward.
4. Save the exact argument string used for dispatch as the prompt-argument capture.
5. Run `scripts/validate_prompt.py` with the role, template, values file, and captured prompt argument. Example:

   ```bash
   python scripts/validate_prompt.py --role discovery \
     --template prompts/discovery-reviewer.md \
     --values audit/D1.values.json \
     --actual-prompt audit/D1.prompt-argument.txt
   ```

After dispatch, replace the capture with the actual serialized prompt argument from the host trace when available and run the validator again. Otherwise record that the capture is the exact immutable argument variable passed to dispatch. Save an audit record for every child: reviewer ID, role, model route, dispatch ID, template path/hash, values hash, rendered prompt hash, prompt-argument capture method, validation result, and fresh-context evidence. If the argument cannot be captured or tied to the dispatch call, mark prompt delivery `unverified`; do not claim template compliance was proven.

After all reviewers are dispatched, run `scripts/validate_dispatch_prompts.py --manifest <dispatch-audit.json>` to validate the complete reviewer set and each captured prompt.

Supply the Discovery output contract in the rendered prompt. A host-native structured-output constraint may also be used, but it does not replace post-response script validation.

### 5. Run Discovery reviews with controlled command execution

Discovery Reviewers may execute relevant commands, tests, builds, static analyzers, benchmarks, and temporary reproduction scripts. They must use judgment and run the narrowest checks that can establish or falsify a technical claim.

Before execution, inspect the command and its scripts/configuration for side effects. Use the policy in `references/validation-execution.md`. In particular:

- allow read-only inspection and bounded local test/build/analyzer commands;
- allow temporary scripts and reproducers in a unique OS temporary directory or verified disposable workspace;
- do not edit reviewed source, permanent tests, project configuration, dependency manifests/lockfiles, generated project assets, or VCS state;
- do not install dependencies, run destructive migrations, deploy, or mutate production/shared services without explicit authorization;
- do not assume a fresh child context has a separate worktree;
- preserve existing files and artifacts; do not perform broad cleanup;
- report exact commands, exit codes, meaningful output, environment, and artifacts.

A lack of command permission or a safe environment must not prevent static Discovery. Continue what can be reviewed and disclose tests that were blocked or skipped. Mark the overall review `PARTIAL` only when the missing check materially limits a conclusion or review coverage.

Read `references/validation-execution.md` before assigning or executing validation work.

### 6. Validate and consolidate Discovery outputs

Preserve every raw Discovery response. Save each raw JSON object separately. Run `scripts/validate_review_output.py` against `schemas/discovery-result.schema.json` for every reviewer. The script must validate JSON syntax, schema constraints, and semantic requirements; do not rely on visual inspection or a model's self-attestation.

If a response is malformed or mechanically invalid, permit one format-only repair using `prompts/response-repair.md`, preserving the original technical content. Re-run the validation script. If it still fails, mark that reviewer output invalid; never treat it as an empty review.

Consolidate only findings with the same root cause and recommendations that are materially the same proposal. Preserve source reviewer IDs, local IDs, locations, and distinct evidence. Assign stable Controller IDs (`C-F-001`, … and `C-R-001`, …). Retain unique single-reviewer candidates. Never use majority voting; reviewer count is not proof.

### 7. Independently verify candidates

If all Discovery reviewers completed the target scope and produced no candidates, record that Verification was not required. Otherwise read `prompts/verification-reviewer.md`, render it with the same baseline package and only the context needed for the candidates, plus the consolidated candidate claims and relevant validation evidence.

Dispatch one fresh Verification context using the parent session's model when available. The Verification Reviewer may run focused tests, builds, analyzers, or temporary reproducers to reproduce or falsify a candidate, following the same validation policy. It must not rely on Discovery consensus, repeat broad discovery, or receive another reviewer's private dialogue.

Save and validate the exact Verification prompt argument with `scripts/validate_prompt.py` using the Verification template. Include that dispatch in the same audit manifest and run `scripts/validate_dispatch_prompts.py`. Preserve the raw Verification response and validate it mechanically:

```bash
python scripts/validate_review_output.py --role verification \
  --schema schemas/verification-result.schema.json \
  --input audit/V1.raw-response.json \
  --expected-candidates audit/expected-candidates.json \
  --report audit/V1.validation.json
```

The expected-candidates manifest contains the Controller's exact Finding and Recommendation IDs. The Controller—not the Reviewer—checks missing, duplicate, or unknown candidate IDs.

Every candidate must receive exactly one assessment. If the parent model cannot be identified/selected or Verification cannot be dispatched, report the limitation and mark the review `PARTIAL`.

### 8. Adjudicate and report

Finding verdicts: `confirmed`, `rejected`, `uncertain`, or `not_verifiable`.

Recommendation verdicts: `worthwhile`, `optional`, `not_better`, `context_dependent`, or `not_verifiable`.

A confirmed Finding requires a credible reachable trigger, specific implementation evidence, and material impact. Lack of reproduction alone does not prove rejection. A pre-existing issue may still be real; introduction attribution is separate from defect truth and severity.

A Recommendation must describe the current approach, a feasible alternative, net benefits, trade-offs, and project fit. Do not assign it a bug severity or report style preference as an improvement.

Read `references/adjudication-and-reporting.md` when candidates exist. The final report must state target/baseline, scope, requested and dispatched model routes, review coverage, confirmed Findings, Recommendations, rejected/uncertain/unverifiable candidates, tests actually run (commands, results, and scope), checks not run and why, prompt-delivery validation, JSON-validation results, and remaining limitations.

## Overall status

- **`COMPLETE`:** every requested model was dispatched to a fresh context; all reviewer prompts passed template-to-dispatch validation; all raw reviewer outputs passed script-based JSON/schema/semantic validation; all requested change scope was reviewed against the baseline package; every candidate was independently verified (or Verification was correctly skipped because there were no candidates); and any non-essential tests not run are explicitly disclosed.
- **`PARTIAL`:** at least one valid review exists, but a requested model/child failed, the actual prompt sent cannot be verified against its template, baseline/diff coverage is incomplete, reviewer JSON failed mechanical validation, Verification is incomplete, a material candidate remains uncertain/unverifiable, or a necessary test could not safely be run.
- **`BLOCKED`:** the target cannot be resolved, no usable baseline/change input exists, fresh child contexts/model-specific dispatch are unavailable, or no valid Discovery output exists.

Do not block solely because the host lacks a per-child permission argument. Do not describe an unvalidated reviewer response as complete. Do not describe `COMPLETE` as defect-free code or merge approval.

## Quality gate

- [ ] Baseline diff and current context were provided; reviewers inspected the diff as primary change evidence.
- [ ] Each requested model had a distinct fresh Discovery context.
- [ ] Actual Discovery and Verification prompt arguments were checked against their templates.
- [ ] Prompt headings, section order, line breaks, values, and output contract match the corresponding template.
- [ ] Reviewers could run safe, relevant tests/scripts; skipped or blocked checks are explained.
- [ ] Commands did not mutate reviewed source, permanent tests/configuration/dependencies, generated project assets, or VCS state.
- [ ] Every raw reviewer JSON was mechanically validated by script.
- [ ] Verification candidate IDs were checked mechanically for missing, duplicate, and unexpected values.
- [ ] Every reported conclusion has code or test evidence and an explicit scope.
- [ ] Final status accurately reflects incomplete prompts, validation, scope, and runtime checks.
