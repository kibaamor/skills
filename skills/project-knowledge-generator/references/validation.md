# Validation and behavioral checks

Read this guide before completing any knowledge-base write and when performing an audit. Validation has two layers: deterministic integrity checks and semantic task checks. Passing the first layer does not establish factual correctness.

## Deterministic helper

Run:

```bash
python3 <skill-directory>/scripts/project_knowledge.py validate \
  --root <repository> \
  --knowledge-dir <knowledge-directory> \
  --require-yaml
```

Validation requires exact top-level `README.md`, `CONTEXT.md`, and `ARCHITECTURE.md` files, source-linked metadata on both canonical topic pages, direct links to both from `README.md`, and metadata on other curated topic pages. Navigation indexes, deterministic files under `generated/`, and ADRs under `decisions/` may retain their native format without frontmatter; declared frontmatter is still validated. The helper also checks local Markdown file and heading links, page reachability, allowed frontmatter fields and types, duplicate IDs, source/test path existence, and candidate staleness. It does not execute documented commands, access external links, interpret source symbols, or edit files.

Completion validation must use `--require-yaml`. Without PyYAML, that invocation fails operationally because required metadata could not be checked. Omitting the flag is allowed only for a degraded diagnostic pass, where link and reachability checks continue and `YAML_CHECKS_SKIPPED` is reported. Treat helper errors as blockers; inspect warnings and stale candidates rather than suppressing them blindly.

## Evidence checks

For every materially changed page:

- Apply [evidence governance](evidence-governance.md) to high-risk and non-obvious claims, ownership, provenance, contradictions, and unknowns.
- Confirm cited paths exist and important symbols can be found in the cited scope.
- Resolve implementation and test anchors in prose, tables, code spans, and metadata as repository-root-relative paths. A broad frontmatter path does not validate a narrower inline path; avoid context-relative shorthand that makes the anchor ambiguous.
- Trace the described happy path plus meaningful failure, retry, authorization, transaction, or asynchronous branches.
- Verify public API, event, schema, and configuration claims against their defining artifacts and consumers.
- Support negative claims such as "no adapter," "no consumer," or "not tested" with repository-wide search, and qualify production, test-only, generated, or external scope precisely.
- Check dependency-direction and coverage summaries against direct imports, calls, test doubles, and actual assertions; a main-flow sketch is not a complete dependency or coverage map.
- Confirm tests and commands exist in the documented invocation context, including relevant runtime/tool version requirements. Inspect test bootstrap, teardown, external dependencies, and data-changing side effects before running; do not let a piped or wrapper command hide the failing step. Run safe, relevant commands when practical; otherwise state why they were not run.
- Check that inferred ownership, dependency direction, or intent is either supported by evidence or explicitly marked unverified.
- Check renamed and removed paths with repository-wide search.
- Inspect the final diff to ensure only authorized knowledge and agent-entry files changed.
- Confirm that a repeated run over unchanged evidence would be content-stable.
- Keep incidental checkout state, such as dependencies currently absent or a temporary clone being clean, in the completion report unless it establishes a durable repository constraint.

Do not copy secret values while checking configuration. Avoid using generated output, vendored dependencies, or mocks as the sole evidence for production behavior.

## Functionality checks

Confirm `CONTEXT.md` states project purpose, audience and scope, stable terminology, a coarse view of current project functionality, important lifecycle conditions, and decision-relevant gaps. Confirm `ARCHITECTURE.md` maps deployable runtimes and major components, boundaries, dependency direction, stores/external systems, representative control/data/event flows, and architectural invariants. Both pages should link focused evidence rather than duplicate it, and both must be reachable directly from the knowledge entrypoint.

State the audience and repository scope covered by the functionality view. For a new knowledge base or full refresh, independently derive capability candidates from the project's maintained public surfaces—such as UI actions, registered routes/APIs, CLI commands, library interfaces, scheduled jobs, event consumers, and acceptance tests—and reconcile them with the knowledge index. In a large repository, reconstruct the top-level surface ledger and, for each deployable or runtime, verify its primary and auxiliary interfaces, applicable health/status/metrics surfaces, and worker/job/event-consumer families are mapped to a capability family or named as an unverified, excluded, or out-of-scope gap. Include registrations embedded in a service process and shared bootstraps that install work in multiple runtimes; do not require every endpoint to have a deep page. For scoped maintenance, reconcile every changed surface and sample the highest-risk unchanged core capabilities.

For each checked capability, verify:

- actor or system trigger, exposed entrypoint, and current availability or lifecycle status;
- every listener, registration, dispatch stage, and gate between an external trigger and the handler's first effective action and observable outcome when routing is dynamic or layered;
- the effective authentication, authorization, or permission chain for each interface family that carries a security claim, without generalizing from adjacent routes or namespaces;
- prerequisites, permissions, flags, configuration, inputs, and important variants when evidenced;
- observable result, state change, side effects, and meaningful failure behavior;
- implementation path and symbol, related contract or invariant, and focused tests or an explicit verification gap.

Check navigation in both directions: functionality view → focused topic → source/tests, and actual registered or reachable entrypoint → capability entry. Do not present planned, dead, internal, gated, or unverified behavior as generally supported. If the discovery scope cannot justify completeness, state the scope and gaps instead of claiming a complete feature catalog.

## Task-route exercises

Test navigation with representative repository-specific questions when the corresponding concerns exist:

1. **Function discovery:** Starting with real user, operator, command, or integration terminology rather than a source symbol, can an agent find the capability, availability conditions, observable behavior, implementation entrypoint, and tests?
2. **Function change:** Given an adjacent change to a real capability's precondition, output, variant, or side effect, can it find the extension point, affected contracts/consumers, invariants, and verification path?
3. **Bug:** Given a real error branch, failing assertion, symptom, or diagnostic signal, can it reach the failure path, side effects, and focused tests?
4. **Cross-cutting change:** Given an actual API, schema, configuration, security, or performance boundary, can it identify upstream/downstream impact and rollback or public-contract compatibility requirements?

Start each exercise at `AGENTS.md` or the knowledge index and route through `CONTEXT.md` or `ARCHITECTURE.md` as appropriate. Record the repository evidence used to choose the scenario, pages traversed, final source/test anchors, and missing steps. Do not count a route as successful if it depends on unguided source search to recover information absent from the knowledge base.

## Audit finding levels

- **Error:** Missing canonical document, unsupported metadata, broken or escaping evidence path, broken local file or heading link, invented executable command, supported-function or key behavior claim contradicted by authoritative evidence, or omitted known high-risk invariant.
- **Warning:** Candidate staleness, missing or unreachable core capability, incomplete task route or verification path, ambiguous authority, or an important unverified claim.
- **Gap:** Useful knowledge not yet established because evidence or scope is unavailable. Gaps are not silently converted into facts.

An audit request is report-only. Present each finding with its page, claim or route, authoritative evidence, consequence for coding agents, and focused repair. Only edit when repair was also requested.

## Completion report

Include:

- scope and repository revision or working-tree state examined;
- files created, updated, or intentionally left unchanged;
- deterministic checks and project commands run, with results;
- representative task routes exercised;
- unresolved gaps, contradictions, skipped checks, and stale candidates.

Do not report a global freshness score or file-coverage percentage as proof of quality. The meaningful outcome is whether an agent can locate change points, impact, constraints, and verification without being misled.
