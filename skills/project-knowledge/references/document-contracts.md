# Document Contracts

Use these contracts as content guides, not rigid fill-in templates. Omit sections with no evidenced, durable information.

## AGENTS.md

`AGENTS.md` is the concise operating manual for coding agents. Instructions in a deeper directory apply to that subtree and may refine root guidance.

Place the primary file at the repository root. Add a nested `AGENTS.md` only when its subtree has materially different commands, constraints, or completion checks; keep shared guidance in the root file.

Include, when evidenced:

- A one-paragraph repository purpose and the locations of `CONTEXT.md` or `CONTEXT-MAP.md`, `ARCHITECTURE.md`, and `CODE-MAP.md`.
- Commands agents must run for setup, focused tests, full tests, linting, type checking, building, or generated artifacts. Prefer manifest/config links when the command is obvious there.
- Repository-specific coding and testing conventions that cannot be inferred cheaply from nearby code.
- Boundaries or files that require special handling, including generated code, migrations, secrets, vendored content, and deployment configuration.
- A completion contract: the checks required before reporting a change complete.

Exclude:

- Generic programming advice and instructions the agent follows by default.
- Large directory trees, dependency inventories, or configuration copied from machine-readable files.
- Domain definitions and architecture narratives; link to their owning documents.
- Aspirational rules contradicted by the current repository unless clearly labelled as a migration target.

Suggested shape:

```md
# Repository Guide

## Start Here
## Commands
## Working Agreements
## Testing
## Boundaries
## Completion
```

## CONTEXT.md

`CONTEXT.md` is a domain glossary. It defines project-specific concepts and the canonical language used for them. It contains no implementation details, workflows, APIs, storage choices, or architecture decisions.

Use this entry shape:

```md
# <Context Name>

<One or two sentences defining this domain boundary.>

## Language

**Canonical term**:
<What the concept is in one or two sentences.>
_Avoid_: <ambiguous or deprecated synonyms>
```

Include only terms whose project-specific meaning matters. Choose one canonical term when synonyms compete. Group terms only when real domain clusters exist.

For a single coherent domain, place `CONTEXT.md` at the repository root. For multiple bounded contexts, place each `CONTEXT.md` at the nearest stable root of its domain area and create a root `CONTEXT-MAP.md`.

## CONTEXT-MAP.md

`CONTEXT-MAP.md` is an index, not a combined glossary. Create it only when at least two genuine bounded contexts exist.

Include:

- Every context's canonical name, relative link, and one-line responsibility.
- Relationships that matter for understanding ownership, language translation, or domain flow.
- Shared concepts and which context owns their definitions.
- Known ambiguous terms whose meaning changes across contexts.

Suggested shape:

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md): receives and tracks customer orders
- [Billing](./src/billing/CONTEXT.md): owns invoices and payment collection

## Relationships

- **Ordering -> Billing**: Billing consumes accepted orders and translates customer references into billing accounts.

## Shared Language

- **Customer ID**: defined by Ordering and consumed unchanged by Billing.
```

Describe relationships in domain terms. Put protocols, queues, endpoints, and data formats in `ARCHITECTURE.md`.

## ARCHITECTURE.md

`ARCHITECTURE.md` explains how the implemented system is shaped and why. Optimize it for change planning, impact analysis, and navigation.

Place it at the repository root. In a monorepo, describe system-wide boundaries there and link to established package-level architecture documents rather than creating new ones without evidence of separate ownership.

Include, when evidenced:

- Scope, system purpose, users, and external systems.
- Major components and their responsibilities, with links to their source roots or entry points.
- Runtime interactions and principal data flows.
- Persistence, messaging, deployment, and process boundaries that affect design or operations.
- Dependency direction, ownership boundaries, and invariants a change must preserve.
- Important rationale and trade-offs that explain surprising structure. Link to ADRs when available.
- Known architectural risks or intentional transitional states, clearly distinguished from the intended architecture.

Use Mermaid only when a diagram communicates topology or flow more clearly than prose. Every diagram must be followed by enough prose to name the responsibility and boundary represented; do not encode critical facts only in a diagram.

Suggested shape:

```md
# Architecture

## System Overview
## Components
## Runtime Flows
## Data And State
## Deployment
## Constraints And Invariants
## Decisions And Trade-offs
## Known Risks
```

Exclude exhaustive file listings, generated dependency graphs, and low-level call sequences. Link to source for details that change frequently.

## CODE-MAP.md

`CODE-MAP.md` is the repository's source navigation index. It answers where an agent should start reading or editing for a responsibility; `ARCHITECTURE.md` remains the owner of system behavior and design rationale. Create it at the repository root and refresh it whenever structural changes make its paths or ownership descriptions stale.

Include, when evidenced:

- Executable entry points and their roles.
- Responsibility-bearing modules or packages, linked to their source roots.
- High-value symbols or files that directly control important behavior.
- The nearest focused tests for each mapped area.
- Generated, vendored, migration, or configuration areas where the edit source differs from the visible output.
- Cross-cutting shared code only where it is a meaningful starting point for changes.

Suggested shape:

```md
# Code Map

## Entry Points
## Modules
## Shared Code
## Tests
## Generated And Special-Handling Areas
```

Prefer short responsibility-to-path entries:

```md
- **Order submission**: [handler](./src/orders/submit.ts), [focused tests](./test/orders/submit.test.ts)
```

Exclude exhaustive directory trees, inventories of every file, low-value utility symbols, and architecture prose. Every linked path must exist. Remove stale entries during maintenance rather than retaining a historical map.

## Cross-Document Ownership

| Knowledge | Owner |
| --- | --- |
| Agent commands, constraints, completion checks | `AGENTS.md` |
| Canonical domain terms and meanings | `CONTEXT.md` |
| Domain boundaries and relationships | `CONTEXT-MAP.md` |
| Components, runtime flows, technology constraints, rationale | `ARCHITECTURE.md` |
| Source locations, entry points, change targets, nearby tests | `CODE-MAP.md` |
| Durable individual design decisions | ADRs |
| Exact scripts, versions, dependencies, schemas | Repository source and configuration |
