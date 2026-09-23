# Adversarial Verification

Apply these checks to the working evidence ledger.

## Commands

- Trace every documented command through its complete script chain to the final executable.
- Run the narrowest safe invocation when prerequisites and authorization are available.
- Record an unverified chain, missing prerequisite, or unsafe side effect as a specific unknown.

## Gated Behavior

- For environment, branch, deployment, security, and feature claims, enumerate configured values and inspect every controlling condition.
- Treat labels such as `production` or `secure` as names, not evidence. Downgrade the claim when any controlling value or condition remains uninspected.

## Domain Definitions

- Confirm cardinality, lifecycle, duration, status, and ownership from behavior-bearing code or focused tests.
- Treat names and prose documentation as leads. When behavior-bearing evidence is incomplete, label the claim as representative or report a specific unknown.

## Runtime Boundaries

For a claim that depends on data or effects crossing a persistence, parser, SDK, cache, queue, transport, or serialization boundary:

- Establish reachability from an actual registration, composition root, or entry point through the producer and consumer. Unreferenced helpers, similarly named adapters, declared schemas or types, hand-built objects, and test-only doubles are candidate evidence, not proof of the running path.
- Compare the reachable producer's runtime type and prototype, intervening transformations, consumer access operations, serializer, and focused-test fixture representation. When a repository-pinned library exposes an installed no-I/O hydrate, parse, or decode path, run its value through the actual consumer and relevant serializer. Record resulting values, exceptions, or exposure surface. Classify a decisive reproduced mismatch as a current defect and trace its downstream consequence; reserve an unknown or guardrail gap for an unavailable or inconclusive probe.
- For ordered effects, label each step as invocation, enqueue, dispatch, remote acceptance, or remote application. An earlier `await` establishes external order only when it completes at the required layer and propagates failure; differing delivery paths, fallback returns, or concurrent replay limit the claim to local invocation order. For multi-step migration or reconciliation, include partial failure and queued replay or concurrency. A mocked call-order test proves only the invocation order implemented by that double; compare its completion semantics with the reachable adapter.
- Trace swallowed errors, batching, retries, acknowledgements, and fallback values back to the caller-visible result. When failure is swallowed or no durable delivery or confirmation guarantee exists, describe caller-visible success as best-effort rather than a successful repair or synchronization. When durable asynchronous acceptance or delivery guarantees are verified, state the accepted or queued state and its guarantee instead of labelling it best-effort.
- If a safe production-shaped or production-path check is unavailable, narrow the published claim and report the representation, completion, ordering, or guardrail gap instead of inferring compatibility.

## Functional Module Boundaries

- Trace at least one real trigger or caller through registration, gates, dispatch, behavior-bearing code, state changes, side effects, and the observable outcome.
- Search repository-wide for competing registrations, callers, consumers, and ownership evidence before claiming the module boundary is complete.
- Treat directory, package, service, and team names as leads. Keep shared infrastructure, other responsibilities, generated output, and external systems as linked boundary owners unless behavior evidence makes them part of the module.

## Counterexamples

- Search the full stated scope for counterexamples to dependency direction, uniqueness, absence, completeness, and isolation claims.
- State the searched scope. Label a partial search as representative rather than complete.

Verification is complete when every high-risk ledger claim passes its applicable checks or is a specific unknown, and every owner document reflects that result. For Functional module scope, this includes module identity, reachability, included anchors, boundary edges, and exclusions.
