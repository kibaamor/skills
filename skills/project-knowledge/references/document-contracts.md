# Document Contracts

Use these contracts as selection and ownership rules, not templates. Omit sections without durable, evidenced information.

## Selection

Create or retain a document only when its value test passes:

- `AGENTS.md`: a repository-specific command, constraint, special-handling rule, completion check, or pointer changes agent behavior.
- `CONTEXT.md`: project-specific terms or boundaries are not safely recoverable from conventional names.
- `CONTEXT-MAP.md`: at least two evidenced bounded contexts use distinct models or conflicting meanings. Directory, package, service, or team count alone is insufficient.
- `ARCHITECTURE.md`: a non-obvious runtime flow, boundary, dependency constraint, external or persistence relationship, or durable rationale helps change planning.
- `CODE-MAP.md`: at least two responsibility-bearing navigation targets exist, or agents must distinguish an edit source from tests, generated output, deployment, or another non-obvious target.

On refresh, preserve a document while its value test holds. Remove a generated document that fails its test only after relocating supported human-authored content to its owner. Report the removal. Never create placeholders.

## Ownership

| Knowledge | Owner |
| --- | --- |
| Runnable commands, handling rules, invariant enforcement, completion checks | `AGENTS.md` |
| Canonical domain terms and meanings | `CONTEXT.md` |
| Domain boundaries, relationships, and term routing | `CONTEXT-MAP.md` |
| Components, runtime flows, design constraints, invariant rationale | `ARCHITECTURE.md` |
| Source locations, entry points, edit/output targets, nearby tests | `CODE-MAP.md` |
| Durable individual design decisions | ADRs |
| Exact scripts, versions, dependencies, schemas | Repository source and configuration |

## AGENTS.md

Place the primary operating guide at the repository root. Add a nested guide only when its subtree has materially different commands, constraints, or completion checks.

Include repository-specific pointers, commands, conventions, special handling, feedback paths, and completion checks. State a rule's trigger, action, prerequisite, and observable completion condition when they are not obvious. Link to manifests, scripts, and deeper knowledge owners instead of copying their contents.

Exclude generic programming advice, broad best-practice reminders, large inventories, domain definitions, architecture narratives, and aspirational rules without a current agent action.

## CONTEXT.md

Define project-specific concepts, canonical terms, ambiguous or deprecated synonyms, and the domain boundary. Keep implementation paths, commands, APIs, storage, protocols, runtime flows, and architecture decisions elsewhere.

Use one root glossary for one coherent domain language. For multiple bounded contexts, place each glossary at the nearest stable domain root and create a root `CONTEXT-MAP.md`. Group terms only when real domain clusters improve retrieval.

Use concise entries:

```md
**Canonical term**:
Definition in one or two sentences.
_Avoid_: ambiguous or deprecated synonym
```

Preserve canonical terms in their source language while writing definitions in the requested output language.

## CONTEXT-MAP.md

Index every context glossary with its canonical name, link, and one-line responsibility. Record relationships, definition ownership, and terms that change meaning across contexts. Describe relationships in domain terms; keep protocols, endpoints, queues, and data formats in `ARCHITECTURE.md`. Do not duplicate glossary definitions.

## ARCHITECTURE.md

At the repository root, describe evidenced components, runtime and data flows, process and deployment boundaries, dependency direction, invariants, external systems, persistence, important rationale, and known risks that affect change planning. Distinguish implemented behavior from target intent.

Link paths to `CODE-MAP.md`, procedures and enforcement to `AGENTS.md`, and detailed decisions to ADRs. Link established package-level architecture documents when separate ownership is evidenced; do not create them solely because packages exist.

Use Mermaid only when an evidenced topology or flow is clearer as a diagram. Explain every critical relationship in prose. Exclude exhaustive file lists, generated dependency graphs, low-level call sequences, and facts recoverable cheaply from source.

## CODE-MAP.md

At the repository root, map responsibilities to useful starting points: executable entry points, controlling modules or symbols, focused tests, shared harnesses, observability or deployment configuration, and generated or special-handling areas. For generated output, identify both the edit source and visible output; keep the procedure in `AGENTS.md`.

Prefer short responsibility-to-path entries:

```md
- **Order submission**: [handler](./src/orders/submit.ts), [focused tests](./test/orders/submit.test.ts)
```

Use canonical responsibility names without redefining them. Every linked path must exist. Remove stale entries. Exclude exhaustive trees, low-value utilities, architecture prose, and domain definitions.
