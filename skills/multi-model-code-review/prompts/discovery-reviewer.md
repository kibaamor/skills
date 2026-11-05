# Discovery Review

## Task

Independently review the supplied change. Identify (1) real defects or material engineering-quality problems and (2) worthwhile non-defect implementation improvements. Judge the implementation against its requirements and actual system context. Do not implement fixes.

## Review target and intended behavior

{{REVIEW_TARGET}}

## Baseline change package

{{BASELINE_CHANGE_PACKAGE}}

The diff/change content is the primary evidence of what changed. Inspect it first. Then inspect current and baseline code as needed to understand execution and attribution. Do not review current files as though they alone represented the change. If the diff or baseline content is incomplete, state exactly what is missing and do not guess which behavior the change introduced.

## Binding requirements and project constraints

{{BINDING_REQUIREMENTS}}

Check each relevant requirement against the changed behavior. Distinguish an explicit requirement from an inference. Identify missing required behavior, contradictory behavior, and unintended side effects.

## Relevant technical context

{{RELEVANT_TECHNICAL_CONTEXT}}

Use only facts supported by the supplied project material. Unknown versions, contracts, or runtime behavior must remain unknown.

## Task-specific review focus

{{TASK_SPECIFIC_REVIEW_FOCUS}}

These checks are derived from the actual change. Apply only those relevant to the changed execution paths. Do not treat this list as a quota or report every theoretical risk.

## Review approach

1. Understand the intended behavior and relevant contracts.
2. Trace changed execution paths through callers, callees, state, resource ownership, error handling, concurrency, persistence, and protocol behavior as relevant.
3. Actively test suspected defects against existing guards, validation, cleanup, retries, synchronization, invariants, and caller assumptions.
4. Evaluate meaningful engineering quality: architecture boundaries, coupling/cohesion, simplicity, maintainability, API design, language/framework idioms, security, performance, reliability, and testability where relevant.
5. For every potential Finding, establish a concrete location, reachable trigger, violated contract/invariant or material engineering weakness, and impact. Exclude unsupported speculation and style preferences.
6. For every potential Recommendation, compare the current approach with a feasible alternative and explain net benefit, trade-offs, effort, migration risk, and project fit.
7. Inspect existing tests and their assertions. A test name is not evidence of coverage. Do not infer historical test-first process from the final diff.
8. Avoid duplicate reports for the same root cause. Preserve independent issues even when only one model identifies them.

## Executable validation

You MAY and SHOULD run focused commands when they materially improve confidence. This includes relevant existing tests, targeted test filters, builds, static analyzers, type checks, race detectors, sanitizers, bounded fuzzing, and temporary reproducer scripts.

Before execution, inspect the command and any invoked script/configuration for side effects. Follow the supplied validation boundary:

{{VALIDATION_BOUNDARY}}

Prefer the narrowest check that can confirm or falsify a concrete hypothesis. Temporary scripts, fixtures, and outputs must use a unique OS temporary directory or verified disposable workspace. Do not modify reviewed source, permanent tests, project configuration, dependency files, generated project assets, or VCS state. Do not install dependencies, deploy, or mutate shared/production services. Do not run destructive or unbounded operations.

For each check, report the exact command/procedure, purpose, environment, exit code/status, actual output summary, scope/assertions, artifacts, and any side effects. If a useful test cannot safely run, state why. Do not claim a test passed unless it actually ran.

## Reportable result categories

### Findings

A Finding is a concrete defect (`kind=defect`) or a material engineering-quality problem (`kind=engineering_quality`). Provide:

- a unique reviewer-local ID such as `F-01`;
- title, kind, and category;
- exact file and line/range;
- code evidence and violated requirement/invariant;
- realistic trigger/scenario;
- concrete impact and severity (`critical`, `high`, `medium`, `low`);
- introduction status (`introduced`, `pre_existing`, or `unknown`) only when baseline evidence supports it;
- confidence (`high`, `medium`, or `low`).

A pre-existing problem may still be a valid Finding if it materially affects the changed behavior or violates a binding requirement. Do not confuse introduction attribution with defect truth.

### Improvement Recommendations

A Recommendation is a non-defect opportunity. Provide a unique local ID such as `R-01`, title, location, current approach, concrete alternative, expected benefits, trade-offs/costs, and why it fits this project. Do not assign severity. Omit cosmetic or low-value suggestions.

## Output format

Return exactly one raw JSON object. No Markdown fences or surrounding prose. Use this shape and the matching field names:

```json
{
  "schema_version": "2.1",
  "reviewer_id": "D1",
  "review_status": "complete",
  "summary": "Concise review summary",
  "scope": "Files and behavior actually reviewed; include exclusions",
  "spec_compliance": [
    {
      "requirement": "Requirement or contract",
      "status": "satisfied",
      "evidence": "Relevant code/test evidence"
    }
  ],
  "findings": [
    {
      "local_id": "F-01",
      "kind": "defect",
      "title": "Concrete issue",
      "category": "correctness",
      "location": "path/file.ext:10-14",
      "evidence": "Exact implementation evidence",
      "trigger": "Reachable trigger or scenario",
      "impact": "Concrete consequence",
      "severity": "high",
      "introduction_status": "introduced",
      "confidence": "high"
    }
  ],
  "recommendations": [
    {
      "local_id": "R-01",
      "title": "Concrete improvement",
      "location": "path/file.ext:20-25",
      "current_approach": "What the code does today",
      "alternative": "Specific feasible alternative",
      "benefits": "Expected net benefit",
      "tradeoffs": "Cost, complexity, migration, or risk",
      "project_fit": "Why it fits this project"
    }
  ],
  "checks": [
    {
      "check_id": "T-01",
      "kind": "test",
      "purpose": "Verify candidate behavior",
      "command": "go test ./path/to/package -run TestCase",
      "status": "passed",
      "exit_code": 0,
      "scope": "Behavior actually exercised and assertions",
      "output_summary": "Relevant observed output",
      "artifacts": [],
      "side_effects": "Temporary test cache only; project and VCS state unchanged"
    }
  ],
  "checks_not_run": [
    {
      "check": "Integration test",
      "reason": "Requires unavailable disposable service"
    }
  ],
  "limitations": []
}
```

Use empty arrays when no items of that category were found after assessing the assigned scope. `checks` records commands that actually ran; do not put proposed commands there. `checks_not_run` records relevant checks not run and why. Do not invent locations or evidence. Do not include chain-of-thought. The Controller assigns global candidate IDs after consolidation.
