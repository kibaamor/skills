# Evidence Governance

Treat existing project knowledge as human-maintained unless a file or delimited region names its generator, or repository configuration or automation declares it replaceable output. A filename, uniform style, or location alone is not provenance. Preserve supported guidance and rationale; verify current-state claims against the project before relying on or revising them.

## Facts and ownership

- Separate **current behavior** (what reachable source, schemas, and checked-in configuration control) from **demonstrated scenarios** (what focused tests assert) and **intent** (accepted decisions, maintained design guidance, ownership, or plans). Correct contradicted current-state prose. Retain contradicted human intent only when still useful, label the conflict, and never present intent as execution evidence.
- Give each durable fact one authoritative owner in the knowledge set. Within the affected scope, update that owner and remove or replace competing copies; other documents should link or summarize without restating the fact as a second authority. Report any consolidation that changes where agents must look.
- Classify conclusions as:
  - **Verified**: directly established by current, reachable source or configuration.
  - **Strong inference**: supported by at least two independent, consistent signals and no counterexample in the stated search scope, with the inference stated explicitly.
  - **Unknown**: evidence is missing, contradictory, environment-dependent, or outside the inspected scope.

## Proportional evidence

Keep a lightweight evidence ledger only for claims that are high-risk, non-obvious, contradicted, or assert completeness or absence. A ledger entry should name the claim, owner document, confidence class, decisive repository-relative paths and symbols, contradiction or source classification when relevant, and any boundary that remains unverified. Routine, locally obvious facts do not need ledger entries.

For runtime and public-surface claims, trace the full command chain: declared command or deployment entrypoint, arguments and environment, gates or feature switches, each dispatcher or registry layer, and the final handler. For multi-stage dispatch, verify every transition rather than treating a handler file as proof of reachability.

For authentication, authorization, and permission claims, trace the effective gate chain at the application, router, route or command, and handler layers for each distinct interface family. Do not infer that an endpoint is protected because a sibling endpoint, namespace, or downstream operation uses a guard. Record meaningful guard differences and qualify any unverified deployment-layer protection.

Record runnable commands only after tracing them through manifests or automation to the final executable. State relevant prerequisites and scope, and run the narrowest safe check when practical.

Before making completeness or negative claims such as "all entrypoints" or "no consumers", perform a scope-wide counterexample check across relevant manifests, scripts, deployment definitions, registries, dynamic loaders, and convention-based discovery. State the searched scope and exclusions when they affect the conclusion.

Keep deterministic generated references separate from curated explanations. Advance `verified_commit` only after semantically reviewing the complete page against that revision; a clean path diff or successful mechanical validation is only a review signal.

## Reporting unknowns

Do not fill gaps with plausible architecture. Report what is unknown, why the available evidence cannot decide it, what was inspected, and the smallest concrete artifact or check that would resolve it. If contradictory evidence exists, preserve the conflict and identify which source governs current execution, if that can be verified.
