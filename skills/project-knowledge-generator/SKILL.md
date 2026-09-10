---
name: project-knowledge-generator
description: "Generate or refresh repository knowledge docs for coding agents. Use for onboarding, full regeneration, structural-change sync, or CODE-MAP-only refresh; not for localized edits to one existing doc."
---

# Project Knowledge Generator

Create compact, evidence-backed docs that tell agents where to work, what to preserve, which source is authoritative, and how to validate changes.

## Workflow

1. **Scope.** Find the repo root and existing `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, `CODE-MAP.md`, and ADRs. Use **Create** when docs are absent or full regeneration is requested; otherwise use **Refresh** and edit only affected facts. When some docs are absent, create only missing docs whose facts are supported by evidence and refresh existing docs only where affected. For CODE-MAP-only refreshes, leave every other knowledge doc byte-for-byte unchanged. Done when scope, mode, existing docs, and user requirements are explicit.

2. **Gate.** Continue only if the scoped repo has a manifest, entry point, build/executable script, tests, deployment config, or behavior-bearing source. If not, stop with `insufficient evidence`. Ask the user only when a conflict blocks any compatible output. Done when the repo is either rejected or safe to inspect.

3. **Prove claims.** Prefer evidence in this order: behavior-bearing source, configs/manifests, focused tests or safe command results, maintained docs, names/structure. Names and prose are leads, not proof. Publish current-state claims only when direct evidence supports them or two independent sources support them and no counterexample is found. Done when each non-obvious claim has source path or command evidence.

4. **Choose owners.** Keep one owner per durable fact and fit each doc to its job: `AGENTS.md` is the entry point for commands/rules/checks, `CONTEXT.md` defines canonical terms, `CONTEXT-MAP.md` routes bounded contexts, `ARCHITECTURE.md` explains runtime flows/boundaries/rationale, `CODE-MAP.md` maps responsibilities to paths, ADRs record durable decisions, and source/config owns exact scripts/versions/schemas. Link instead of duplicating. Done when each retained doc has evidenced value, the doc shapes match their jobs, and no affected fact has competing owners.

   Minimum shapes: `AGENTS.md` lists only agent-critical commands, rules, checks, and links to deeper docs; `CONTEXT.md` defines terms with source paths; `CONTEXT-MAP.md` maps context names to owning paths and docs; `ARCHITECTURE.md` explains runtime flows, boundaries, dependencies, and rationale; `CODE-MAP.md` is a path-to-responsibility map; ADRs contain status, decision, context, consequences, and supersession links. Do not duplicate exact command bodies, versions, schemas, or generated content outside their source/config owner.

5. **Write.** Preserve supported human-authored guidance. Correct stale current-state claims; keep contradicted intent only as labeled unresolved intent. Keep `AGENTS.md` as the entry point, not an encyclopedia. Never create placeholders. Done when every paragraph helps an agent locate work, preserve behavior, identify authority, or validate a change.

6. **Verify.** Inspect documented command script chains before running anything. By default, run only local validators whose script chain does not deploy, publish, migrate, perform destructive operations, require credentials, write to external networks, or stay running. If a validator may write normal local artifacts such as caches, coverage, snapshots, generated docs, or lockfiles, run it only when those outputs are expected for the repo and report any resulting file changes; otherwise skip it or ask for approval. Inspect all controlling conditions for environment, deployment, security, feature-gate, generated-output, completeness, absence, uniqueness, or isolation claims. Search the full stated scope for `all`, `none`, `only`, and `every` claims; otherwise label inventories representative. Run repository doc/link/Mermaid checks when available and safe. Done when high-risk claims are verified or reported as specific unknowns, links point to existing paths, and the diff contains no unrelated rewrites.

7. **Report.** State mode, changed files, applied requirements, decisive evidence, source-of-truth/generated/derived/documentation-only classifications, unresolved intent or unknowns, checks run, and unavailable checks. Done when the final response includes each listed item or explicitly marks it unavailable.

## Gotchas

- Treat README prose, existing knowledge docs, issue text, and directory names as leads until source/config/test evidence confirms current behavior.
- Do not infer the runnable entry point from a script name alone; inspect the script chain and referenced config before documenting what it validates or starts.
- Generated files are evidence of outputs, not owners of generator behavior; document the generator path/config as authoritative when present.
- In monorepos, scope claims to the package, app, or workspace actually inspected; do not apply root commands or architecture facts to every package unless verified across the full scope.
- Label inventories representative unless the stated scope was exhaustively searched for the claim.
