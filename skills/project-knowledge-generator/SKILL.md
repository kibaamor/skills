---
name: project-knowledge-generator
description: Use this skill when the requested deliverable is a durable, repository-local knowledge base for coding agents, including creating it, maintaining it after source changes, auditing it against repository evidence, or repairing confirmed knowledge drift. Do not use it for chat-only repository explanations, standalone README/API/architecture documentation outside that knowledge base, source indexes or RAG stores, generic documentation reviews, product-code work unless the knowledge base is also requested, or migration of an older knowledge-base layout.
---

# Project Knowledge Generator

Build a compact navigation and constraint layer that helps a coding agent understand what the project does, locate the capability and implementation responsible for a behavior, assess change impact, and verify work. Preserve the project's documentation language and supported guidance unless the user requests otherwise.

## Route the request

- **Create:** Read [references/content-model.md](references/content-model.md). Bootstrap a knowledge base when the target knowledge root is absent.
- **Maintain:** Read [references/maintenance.md](references/maintenance.md). Maintain only a knowledge base whose root already contains `README.md`, `CONTEXT.md`, and `ARCHITECTURE.md` with the required direct links; read the content model too when adding a new knowledge area.
- **Audit:** Read [references/validation.md](references/validation.md). An audit is read-only unless the user also asks to repair findings. For repairs, also read the maintenance guide.
- **Mixed:** Audit the existing knowledge first, then follow the matching Create or Maintain route for confirmed gaps.

## Boundaries

- Resolve the repository, monorepo, or package scope before working. Honor a user-specified knowledge location; otherwise preserve an existing location or use `docs/project-knowledge/` as the fallback.
- By default, change only the knowledge base and the smallest applicable agent-entry link needed to make it discoverable. Do not change product source, dependencies, runtime configuration, or external indexes unless the user asks.
- Do not replace or weaken existing `AGENTS.md` instructions. When creating a new agent-facing knowledge base, append only a concise pointer to the applicable existing agent entrypoint unless the user excludes that file; if no entrypoint can be changed, report the unlinked discovery path.
- Preserve unrelated and uncommitted work. Inspect changes before editing and keep maintenance patches limited to affected knowledge.
- Use only the current knowledge contract. Do not detect knowledge-base versions, interpret older layouts, migrate or upgrade them, or add compatibility shims. If an existing target does not satisfy the Maintain precondition, report that it is outside this skill's scope and leave it unchanged.
- Do not read or reproduce secrets, local environment values, real user data, dependency trees, generated output, or vendored code merely to increase coverage.
- Do not publish to a vector database, wiki, or other external system without separate authorization. Markdown in version control remains the reviewable source; retrieval indexes are derived artifacts.

## Shared workflow

1. **Establish scope and instructions.** Locate the repository root and applicable `AGENTS.md` files. Inspect the current worktree, existing knowledge, architecture records, and documentation conventions. In a monorepo, decide whether the request targets the root, one package, or shared behavior.
2. **Inventory breadth-first and set a depth boundary.** Inspect tracked manifests, source and test roots, schemas, configuration definitions, CI/deployment files, runtime entrypoints, ADRs, and existing docs. Identify functionality candidates from maintained product docs, UI navigation and actions, registered HTTP/RPC routes, public APIs, CLI commands, scheduled jobs, event consumers, feature flags, permissions, and acceptance tests when those surfaces exist. Skip caches, build output, vendored dependencies, binaries, and secret-bearing local files. For a large or unfamiliar repository, run [scripts/project_knowledge.py](scripts/project_knowledge.py) in inventory mode before focused reading:

   ```bash
   python3 <skill-directory>/scripts/project_knowledge.py inventory --root <repository> --format text
   ```

   Add `--include-untracked` only when untracked files are part of the requested working-tree scope. Before deep tracing a large repository, follow the coverage-ledger and depth-boundary guidance in the content model; map interface families rather than enumerating endpoints merely to prove breadth.
3. **Build an evidence map.** Read [references/evidence-governance.md](references/evidence-governance.md). Identify the goals the project enables for users, operators, API/library consumers, integrations, or system actors. Connect each confirmed capability to its exposed trigger, observable result, implementation entrypoints, state changes and side effects, contracts, constraints, and tests. Follow critical request, event, state, and data flows far enough to identify boundaries. Use the reference's lightweight claim ledger only for high-risk or non-obvious claims.
4. **Select durable knowledge.** Every knowledge base created or maintained by this skill must include exact, root-level `CONTEXT.md` and `ARCHITECTURE.md` files, both linked from its entry page. `CONTEXT.md` owns the project purpose, actors, scope, terminology, and project-level functionality view; `ARCHITECTURE.md` owns the runtime/component map, boundaries, dependency direction, and key control/data flows. Keep both canonical files concise and link focused pages instead of duplicating their detail. Also include task routing, contracts, invariants, change impact, failure signals, and verification paths where they add decision value. Organize capabilities by stable outcome or journey, not by source directory, class, screen, or endpoint. Do not restate implementation that an agent can read directly.
5. **Write for progressive disclosure.** Keep the root entry short, link to focused topic pages, and create only sections justified by the repository. Give each durable fact one owner and link to it instead of copying it. Prefer path plus symbol references over line numbers. Reuse authoritative existing docs instead of duplicating them.
6. **Verify against evidence.** Before completing any write, read [references/validation.md](references/validation.md). Re-open every changed claim against code, tests, schemas, configuration, or accepted decisions. Run the deterministic helper when applicable, then perform the semantic and task-route checks; mechanical success cannot prove factual correctness.
7. **Report the result.** State the created or updated files, covered scope, evidence and checks used, and any unverified gaps or stale candidates. For an audit, distinguish findings from proposed repairs.

## Completion standard

The knowledge base is useful when a coding agent can start at its entrypoint and, with few hops, answer: what the project enables and for whom; which capability or journey owns a behavior; where a change begins; which components or contracts it affects; which invariants it must preserve; and how to verify it. Missing `CONTEXT.md` or `ARCHITECTURE.md`, a missing functionality view, broken evidence links, invented commands, unresolved contradictions in critical behavior, or omitted known high-risk constraints block completion; unavailable optional checks must be reported as limitations.
