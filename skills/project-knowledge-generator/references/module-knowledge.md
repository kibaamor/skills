# Functional Module Knowledge

Read this reference only when the user requests a dedicated knowledge base for a functional module inside a repository. A functional module is a stable responsibility or actor/system outcome; a directory, package, service, technical layer, or team boundary is not sufficient evidence by itself.

## Establish the Boundary

Use the user's module name as a search seed. Confirm the canonical responsibility from an evidenced trigger or caller, reachable entry point, behavior-bearing control path, observable outcome, and focused validation when available.

Include the control points, owned state or outputs, side effects, and tests needed to change that responsibility safely. Stop at shared infrastructure, another functional responsibility, generated output, or an external system. Record those as boundary edges with links to their owner rather than importing their facts. The resulting module may span directories or packages.

Search the repository for registrations, callers, consumers, and counterexamples before claiming the boundary is complete. Ask one focused question only when multiple evidenced boundaries would materially change ownership or the knowledge location; otherwise use the strongest evidenced boundary and report the uncertainty.

## Place and Link the Knowledge Set

Choose the module knowledge root in this order:

1. A user-specified location.
2. A repository configuration that explicitly declares an authoritative module knowledge root.
3. The existing location for that module on Refresh or full regeneration.
4. A non-binding repository convention for module knowledge.
5. `docs/project-knowledge/modules/<module-key>/`.

Derive `<module-key>` from the repository's canonical module name and naming convention. Keep an existing key stable on Refresh or full regeneration even when display terminology changes; move it only when the user requests a move or repository configuration explicitly makes another location authoritative. A naming convention alone does not trigger migration.

Place `MODULE.md` and any value-tested module documents in that root. Keep operational instructions in the root or source-subtree `AGENTS.md` whose scope actually applies; do not place an `AGENTS.md` inside the central module knowledge directory.

Make the module discoverable through one concise, conditional pointer in the repository's declared knowledge index or the applicable `AGENTS.md`, preserving all existing guidance. If neither exists, create a root `AGENTS.md` containing the pointer when its repository-wide scope is correct. Do not create a separate module registry unless the repository already uses one. If the user excludes every applicable entry document, leave the knowledge set unlinked and report that discovery gap.

## Preserve Ownership

Repository documents own repository-wide terminology, topology, shared constraints, and cross-module relationships. Module documents own only the selected module's identity, internal behavior, local terminology, internal flow, and source navigation. The applicable root or source-subtree `AGENTS.md` owns module-specific commands, rules, and completion checks. Shared components and other modules remain with their existing owner; link to them.

Create `MODULE.md` after the module sufficiency gate passes. Apply the remaining [document contracts](./document-contracts.md) within the selected module scope and create only the documents whose value tests pass. A module is not automatically a bounded context, so its existence alone does not justify a `CONTEXT.md`.

`CONTEXT-MAP.md` remains a repository-level owner. When a value-tested module `CONTEXT.md` adds or changes a bounded-context glossary that the map must index, select the root map as a linked owner and make only the required index or relationship update. Otherwise leave it unchanged and link it when relevant. CODE-MAP-only work never changes it.

## Apply the Mode

- **Create:** Use when this module knowledge set is absent or the user requests full regeneration, even if repository knowledge already exists. For full regeneration, use the knowledge root and key selected by the placement priority above, then rebuild the selected module set from current evidence while preserving supported human-authored guidance and rationale. Create or rebuild `MODULE.md`, value-tested supporting documents, any required root `CONTEXT-MAP.md` update, and any evidenced module-specific commands, rules, or checks in the applicable `AGENTS.md`. Add the minimal discovery pointer unless the user excluded every applicable entry document.
- **Refresh:** Use the knowledge root and key selected by the placement priority above. Use Git changes as leads, then inspect the full evidenced module surface and boundary edges affected by the change. Modify only affected module facts, any required root `CONTEXT-MAP.md` update, an affected pointer in the declared knowledge index, and affected pointers, commands, rules, or checks in the applicable `AGENTS.md`.
- **CODE-MAP-only:** Create or refresh only the selected module's `CODE-MAP.md`. Keep `MODULE.md`, discovery pointers, root knowledge, and every other module document byte-for-byte unchanged; report any missing `MODULE.md`, stale boundary, or missing pointer as a gap.

Full module work is complete when an agent can start from the discovery pointer and determine the module's responsibility and exclusions, trace a real trigger to its observable outcome, find the controlling source and either focused checks or a reported guardrail gap when no focused check exists, identify boundary owners and side effects, and do so without relying on duplicated repository-wide facts. If the user excluded every applicable entry document, the reported discovery gap replaces only the discovery-pointer part of this condition.

CODE-MAP-only work is complete when the selected module's available responsibility-to-source and test links are current, every other knowledge document is byte-for-byte unchanged, and any pre-existing missing or stale `MODULE.md`, discovery pointer, or boundary claim is reported as a gap.
