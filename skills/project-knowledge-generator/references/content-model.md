# Content model

Read this guide when creating a knowledge base or adding a new knowledge area to one that already follows this contract. Adapt optional pages to the repository, but always use the canonical root files defined below.

## Knowledge contract

Project knowledge should explain what source inspection alone makes expensive to rediscover:

- what goals the project currently enables for users, operators, API or library consumers, integrations, and system actors;
- how an agent routes from a task or symptom to implementation;
- where system, domain, data, and ownership boundaries lie;
- how important requests, events, state changes, and side effects flow;
- which behavioral, public-contract compatibility, security, and consistency invariants apply;
- what else a change can affect and how to verify it;
- why a still-relevant architectural choice was made.

Do not copy source listings, generated API specifications, dependency catalogs, or prose already maintained elsewhere. Link to an authoritative artifact and add only the context needed to use it safely.

## Adaptive layout

Use the smallest structure that provides clear task routes. A useful fallback is:

```text
AGENTS.md                         # Short pointer when applicable; preserve existing rules
docs/project-knowledge/
├── README.md                     # Required entry and task-oriented index
├── CONTEXT.md                    # Required purpose, actors, scope, terminology, and functionality
├── ARCHITECTURE.md               # Required runtimes, components, boundaries, dependencies, and flows
├── features/                     # Optional detailed capability pages for a large project
│   └── README.md                 # Detailed capability index when CONTEXT.md would become too large
├── development.md                # Evidence-backed setup, commands, and test strategy
├── areas/
│   └── <area>.md                 # Important domain or component pages only
├── contracts/
│   └── <contract>.md             # Only when contracts need explanation beyond specs
├── operations.md                 # Only when runtime diagnosis/deployment is relevant
├── decisions/
│   └── ADR-NNN-<decision>.md     # Only decisions still affecting the implementation
└── generated/                    # Replaceable deterministic references, if any
```

Every knowledge base uses the exact, case-sensitive top-level names `README.md`, `CONTEXT.md`, and `ARCHITECTURE.md`. The latter two are curated topic pages with source-linked metadata, and `README.md` must link them directly. This skill operates only on this layout.

`CONTEXT.md` answers why the project exists and what it currently enables. It states the audience and repository scope, project purpose, actors, stable terminology, a project-level functionality view, important lifecycle conditions, and decision-relevant coverage gaps. A small project can keep the complete compact capability view there. A larger project keeps a coarse capability map in `CONTEXT.md` and links to `features.md`, `features/README.md`, or focused capability pages for detail. A monorepo usually needs a root capability map and shared constraints, with package-level knowledge close to each package.

`ARCHITECTURE.md` answers how the project delivers those capabilities. It maps deployable runtimes and major packages/components, ownership and trust boundaries, dependency direction, persistent stores and external systems, and representative control/data/event flows. It names cross-cutting architectural invariants and routes readers to detailed area, contract, operation, and decision pages. Keep it a decision-oriented map rather than a directory or dependency dump.

Do not create other empty directories or placeholder pages.

Keep the index oriented around tasks rather than a flat file list. Useful routes include:

- actor goal or project capability → observable behavior → implementation and tests;
- symptom or error signal → area → entry symbol → flow → tests or runbook;
- requested behavior → domain flow → contract/data → implementation → validation;
- path or symbol → owning area → upstream/downstream dependencies → constraints;
- performance target → baseline/telemetry → hot path → invariants → benchmark and rollback.

## Coverage and depth in large repositories

Separate breadth from depth. A first-pass knowledge base for a large or legacy system should make every discovered deployable/runtime surface and public interface family visible at a coarse capability level, but it does not need a deep page for every endpoint or handler.

Use a temporary coverage ledger while investigating. For each service or application runtime, record its primary protocols and interfaces, auxiliary health/status/metrics surfaces, and owned worker/job/event-consumer families. Include work started inside a service process, registrations installed by shared bootstrap modules in several runtimes, and runtime-local schedulers or consumers; do not assume the runtime's primary protocol represents all of its behavior. Also cover standalone workers, jobs, CLIs, library entrypoints, and other public surfaces. Record the evidence that makes each family reachable and map it to one or more stable capability families. In the published scope note, state which surfaces were traced deeply, which were only mapped, and which remain unverified or excluded. Do not expose internal planning detail that adds no navigation value.

Trace high-risk, cross-boundary, frequently changed, or representative capabilities first. Once every discovered top-level surface is mapped or named as a gap, write and validate the useful first pass before expanding lower-value detail. Never claim exhaustive functionality merely because all directories or specification entries were scanned.

## Functionality view

Model functionality by stable actor goal, domain capability, or end-to-end journey. Do not promote every screen, route, endpoint, handler, class, or helper into a peer-level project feature. For libraries and developer tools, the actor may be an API consumer or developer; for services and infrastructure, it may be an integration, scheduled trigger, or operator.

For each confirmed capability, make the following discoverable without duplicating its detailed topic page:

- capability name and the actor or system trigger it serves;
- primary scenario, exposed surface such as UI/API/CLI/job/event, and caller-visible result;
- important internal state changes, side effects, failure outcomes, and variants, clearly separated from what the caller receives;
- evidenced permissions, feature flags, configuration, platform, or lifecycle conditions;
- the first useful area, flow, or contract page plus implementation paths and symbols;
- focused tests or explicit verification gaps;
- supported, experimental, gated, deprecated, internal, planned, or unverified status only when authoritative evidence establishes it.

A compact index can use this shape and link detail elsewhere:

| Capability | Actor or trigger | Caller-visible result | State and side effects | Conditions | Implementation/tests |
|---|---|---|---|---|---|
| Stable goal-oriented name | User, operator, integration, command, job, or event | Returned or externally observed result | Internal change and external effects | Permission, flag, config, or limitation | Topic link, paths, symbols, tests |

Keep this as one compact summary row per capability. Link to detailed branch matrices, change impact, and full test discussion instead of reproducing them in the functionality view. Avoid wording that makes an internal mutation sound like a returned value or an unregistered handler sound network-accessible.

Derive candidates from maintained product documentation, UI labels and navigation, registered routes and commands, API schemas, scheduled jobs, event consumers, and acceptance tests. Then trace from a registered or otherwise reachable entrypoint through domain behavior, state changes, side effects, and failure branches. Cross-check contracts, permissions, flags, configuration, and focused tests.

No single artifact proves a supported function: documentation may be stale, a registered route may be gated or incomplete, a test proves only its asserted scenario, and an internal handler or dead code may not be exposed. Record conflicts or insufficient evidence as documented-but-unconfirmed or unverified. Keep planned capabilities separate from current functionality and do not claim the catalog is exhaustive unless its scope and discovery method justify that claim.

## Metadata for the knowledge base

Use simple YAML frontmatter on focused topic pages, including `CONTEXT.md` and `ARCHITECTURE.md`.

```yaml
---
id: orders.payment-confirmation
summary: Payment confirmation flow and its order consistency constraints.
read_when:
  - Changing payment callbacks, retries, or paid order transitions.
source_paths:
  - src/orders/**
  - src/payments/**
source_symbols:
  - ConfirmPayment
  - PaymentSucceeded
tests:
  - tests/payments/**
verified_commit: 0123456789abcdef
owner: orders-team
---
```

Required for curated topic pages other than navigation indexes, deterministic files under `generated/`, and ADRs under `decisions/`:

- `id`: stable repository-unique identifier using lowercase letters, digits, dots, `_`, or `-`;
- `summary`: one sentence describing the page's decision value;
- `source_paths`: repository-relative files, directories, or narrow POSIX globs that support the page.

Optional fields are `read_when`, `source_symbols`, `tests`, `verified_commit`, and `owner`. List fields contain non-empty strings; `verified_commit` and `owner`, when present, are non-empty strings. Paths must not be absolute or escape the repository. Keep symbols separate from paths. Other frontmatter fields are unsupported. Do not add a permanently optimistic `fresh` label; compute stale candidates from evidence changes instead.

The exempt document classes may omit frontmatter so existing indexes, generated references, and decision records remain in their native format. If they declare frontmatter, it must still use the fields and types above.

`verified_commit` means the complete page was semantically checked against that revision. Omit it when that did not happen. Do not maintain a second handwritten catalog containing the same metadata; derive indexes when automation needs one.

## Index content

The knowledge root `README.md` should contain:

1. a short project and knowledge-scope statement;
2. direct links to required `CONTEXT.md` and `ARCHITECTURE.md`, with `CONTEXT.md` providing the project-level functionality view;
3. a table routing realistic bug, feature, contract, and operational tasks to the first useful page;
4. links to system, area, contract, engineering, and operations knowledge that actually exists;
5. the authority relationship among code, tests, schemas/configuration, ADRs, and this knowledge layer;
6. only the known gaps that can change an agent's decisions.

When an applicable agent-instruction entrypoint already exists, make a newly created agent knowledge base discoverable from it unless the user excludes that file. Append only a short link and preserve all existing rules. Create a new root `AGENTS.md` only when that entrypoint is appropriate to the repository and request. Put explanations in the knowledge base.

## Topic-page content

Use these sections as questions, not mandatory headings:

- **Scope and boundaries:** What does this area own, and explicitly not own?
- **Capabilities and actors:** Which project outcomes or journeys does this area implement, expose, or support?
- **Entrypoints and main flows:** Which paths and symbols begin the behavior? How does control or data move?
- **Contracts and invariants:** Which API, event, data, permission, transaction, ordering, and product-compatibility rules must hold?
- **Dependencies and side effects:** Which consumers, stores, jobs, external systems, or asynchronous paths participate?
- **Change impact:** What else must be inspected when this area changes?
- **Failure and diagnosis:** Which symptoms, error codes, logs, or metrics distinguish common failure modes?
- **Verification:** Which focused tests, commands, observations, and failure criteria validate a change?
- **Unverified gaps:** What cannot be confirmed from available evidence?

Omit irrelevant sections. Split a page when unrelated tasks would otherwise load substantial irrelevant context. Merge tiny pages that agents always need together.

## Evidence and safety

- Apply [evidence governance](evidence-governance.md) when selecting, owning, and verifying claims.
- Cite repository-relative paths and stable symbols; avoid volatile line numbers.
- Name configuration variables and their purpose, but never copy secret or environment-specific values.
- Describe current behavior, not a change log. Keep historical rationale in ADRs and mark superseded decisions rather than rewriting history.
- Treat generated, vendored, cached, and build-output files as secondary evidence unless they define a published contract or build boundary.
- Match the project's established terminology and documentation language. Add glossary mappings only where business, legacy, and code terms differ enough to impair search.
