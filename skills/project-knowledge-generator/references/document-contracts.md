# Document Contracts

Use these contracts as selection and ownership rules, not templates. Apply them to the selected repository or functional-module scope and omit sections without durable, evidenced information.

## Selection

Create or retain a document only when its value test passes:

- `AGENTS.md`: a repository-wide or directory-scoped command, constraint, special-handling rule, completion check, or pointer changes agent behavior. A module-specific rule alone belongs in `MODULE.md`.
- `MODULE.md`: A full Functional module knowledge set has an evidenced canonical responsibility, reachable behavior, observable outcome, and boundary that agents need as a durable entry point. A CODE-MAP-only request does not create or modify it.
- `CONTEXT.md`: selected-scope terms or boundaries are not safely recoverable from conventional names. Qualifying evidence includes ambiguous, deprecated, canonical, lifecycle, ownership, cardinality, or bounded-context language that source names alone would not explain. Do not create a glossary that only restates obvious module, function, class, route, or test names.
- `CONTEXT-MAP.md`: the repository has at least two evidenced bounded contexts that use distinct models or conflicting meanings. A module request selects it only as a linked owner when the selected module glossary changes its index or relationships. Directory, package, service, team, or functional-module count alone is insufficient.
- `ARCHITECTURE.md`: a non-obvious runtime flow, boundary, dependency constraint, external or persistence relationship, or durable rationale helps change planning.
- `CODE-MAP.md`: at least two responsibility-bearing navigation targets exist, or agents must distinguish an edit source from tests, generated output, deployment, or another non-obvious target.

On refresh, preserve a document while its value test holds. Remove a generated document that fails its test only after relocating supported human-authored content to its owner. Report the removal. Never create placeholders.

## Scope Partition

**Managed project knowledge** includes the standard knowledge documents governed by these contracts, user-named knowledge outputs, and documents that repository configuration, scripts, or a discovered knowledge entry point explicitly declares as a knowledge index, root, or owner. Include knowledge owner documents under a declared root. Ordinary README, product, design, planning, and delivery documents are evidence inputs unless one of those signals assigns them a knowledge role; their module facts may seed module knowledge without making the evidence document an edit target.

Classify every durable fact before choosing its document:

- **Module-local** knowledge belongs exclusively to the functional module knowledge set. This includes the module's identity and responsibility, triggers and outcomes, internal behavior and flows, local terms, constraints and rationale, module-specific commands and checks, and its source and test navigation. Keep a durable individual decision in its module-scoped ADR and link it from the module set.
- **Project-level** knowledge covers repository-wide operation, shared infrastructure, and facts that apply independently of any one functional module. It represents existing module knowledge sets only through one authoritative **module map**.

Use the repository's declared project knowledge index as the module map. Otherwise use the applicable root `AGENTS.md`. Each module appears once, as a concise conditional pointer containing its canonical name, when to read it, and a link to its `MODULE.md`. Other project-level documents link to that map when module discovery is relevant. Do not create an empty map when no module knowledge set exists.

Outside CODE-MAP-only work, every module-local fact found in managed project-level knowledge is a structural ownership violation. Apply the functional-module sufficiency gate and value tests, create a missing module set when the gate passes, move supported knowledge to the module owner, and reduce the project-level copy to the map entry. Decompose mixed passages into claims before moving or removing them.

An **ownership blocker** exists when a module-local claim that the preservation rules require retaining has no valid module owner because the sufficiency gate or value tests fail. Preserve the claim in its existing document and report the blocker. Do not delete the claim, create a speculative module set or map entry, or claim that the scope partition is complete. Correct or remove only claims that the evidence and preservation rules do not require retaining. In CODE-MAP-only work, change only the selected `CODE-MAP.md` and report ownership gaps elsewhere.

## Ownership

| Knowledge | Owner |
| --- | --- |
| Repository-wide commands, handling rules, invariant enforcement, completion checks | Applicable root or source-subtree `AGENTS.md` |
| Functional module identity, responsibility, actor or system triggers, observable outcomes, boundary, exclusions, module-specific commands, rules, and completion checks | `MODULE.md` |
| Canonical domain terms and meanings | `CONTEXT.md` |
| Domain boundaries, relationships, and term routing | `CONTEXT-MAP.md` |
| Components, runtime flows, design constraints, invariant rationale | `ARCHITECTURE.md` |
| Source locations, entry points, edit/output targets, nearby tests | `CODE-MAP.md` |
| Durable individual design decisions | ADRs |
| Exact scripts, versions, dependencies, schemas | Repository source and configuration |

## Scope and Placement

For Repository scope, keep the primary `AGENTS.md`, `ARCHITECTURE.md`, and `CODE-MAP.md` at the repository root. Existing nested documents remain valid when their contracts and local scope still hold.

For Functional module scope, keep `MODULE.md` and value-tested `CONTEXT.md`, `ARCHITECTURE.md`, and `CODE-MAP.md` together in the module knowledge root selected by [module knowledge](./module-knowledge.md). Keep repository-wide or directory-scoped `AGENTS.md` at the repository root or the actual source subtree where its instructions apply, not in a central documentation directory. Keep module-specific operation and validation knowledge in `MODULE.md`. Keep `CONTEXT-MAP.md` at the repository root; update it during module work only when the selected module glossary changes the bounded-context index or relationships it owns.

Project-level documents own repository-wide facts and shared infrastructure. Their only compliant module-local content is the authoritative module map; a preserved ownership blocker remains an explicitly reported violation, not an alternate owner. Module documents own module-local facts and link to repository, shared-component, or other-module owners instead of duplicating them.

## MODULE.md

Use `MODULE.md` only as the entry point for a functional module knowledge set. State the canonical module name, responsibility, actors or system triggers, caller-visible outcomes, included behavior anchors, explicit boundary or exclusions, module-specific commands, handling rules and completion checks, and links to its selected documents and external knowledge owners. Distinguish internal side effects from caller-visible results and label gated, deprecated, planned, or unverified behavior only when authoritative evidence supports the status.

Keep repository-wide commands and directory-scoped operating rules in the applicable `AGENTS.md`, detailed flows in module `ARCHITECTURE.md`, navigation targets in module `CODE-MAP.md`, and domain definitions in the owning `CONTEXT.md`. Exclude exhaustive file lists, duplicated repository-wide facts, and implementation detail that source reveals cheaply.

## AGENTS.md

Place the primary operating guide at the repository root. Add a nested guide only when its subtree has materially different commands, constraints, or completion checks.

Include the authoritative module map when `AGENTS.md` owns it, plus repository-wide pointers, commands, conventions, special handling, feedback paths, and completion checks. State a rule's trigger, action, prerequisite, and observable completion condition when they are not obvious. Link to manifests, scripts, and deeper knowledge owners instead of copying their contents.

Exclude generic programming advice, broad best-practice reminders, large inventories, domain definitions, architecture narratives, module-specific operation or validation knowledge, and aspirational rules without a current agent action.

## CONTEXT.md

Define selected-scope concepts, canonical terms, ambiguous or deprecated synonyms, and the domain boundary. Keep implementation paths, commands, APIs, storage, protocols, runtime flows, and architecture decisions elsewhere.

Use one root glossary for one coherent repository domain language. For multiple bounded contexts, place each glossary at the nearest stable domain or module knowledge root and maintain a repository-root `CONTEXT-MAP.md`. A functional module receives its own glossary only when its terms pass the value test; select the root context map as a linked owner when that glossary changes the index or relationships it owns. Group terms only when real domain clusters improve retrieval.

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

For Repository scope, describe evidenced shared infrastructure, process and deployment boundaries, project-wide dependency constraints, external systems, persistence, important rationale, and known risks that apply independently of one functional module. Represent functional modules through the authoritative module map; keep their triggers, outcomes, internal flows, constraints, and rationale in their module knowledge sets. For Functional module scope, describe only the module's internal flow, dependencies, side effects, boundary crossings, invariants, and rationale that agents need to change it safely. Distinguish implemented behavior from target intent.

Link paths to the selected scope's `CODE-MAP.md` and detailed decisions to ADRs. Link repository-wide and directory-scoped procedures to the applicable `AGENTS.md`; link module-specific procedures to `MODULE.md`. Link established package-level architecture documents when separate ownership is evidenced; do not create them solely because packages exist.

Use Mermaid only when an evidenced topology or flow is clearer as a diagram. Explain every critical relationship in prose. Exclude exhaustive file lists, generated dependency graphs, low-level call sequences, and facts recoverable cheaply from source.

## CODE-MAP.md

Map responsibilities within the selected scope to useful starting points: executable entry points, controlling modules or symbols, focused tests, shared harnesses, observability or deployment configuration, and generated or special-handling areas. In Repository scope, map only repository-wide and shared responsibilities; route functional-module navigation through the authoritative module map. A functional module's `CODE-MAP.md` may link registrations or dependencies outside its knowledge root while keeping ownership with their repository or module document. For generated output, identify both the edit source and visible output; keep a repository-wide procedure in `AGENTS.md` and a module-specific procedure in `MODULE.md`.

Prefer short responsibility-to-path entries:

```md
- **Order submission**: [handler](./src/orders/submit.ts), [focused tests](./test/orders/submit.test.ts)
```

Use canonical responsibility names without redefining them. Every linked path must exist. Remove stale entries. Exclude exhaustive trees, low-value utilities, architecture prose, and domain definitions.
