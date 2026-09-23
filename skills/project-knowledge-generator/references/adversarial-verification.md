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

## Functional Module Boundaries

- Trace at least one real trigger or caller through registration, gates, dispatch, behavior-bearing code, state changes, side effects, and the observable outcome.
- Search repository-wide for competing registrations, callers, consumers, and ownership evidence before claiming the module boundary is complete.
- Treat directory, package, service, and team names as leads. Keep shared infrastructure, other responsibilities, generated output, and external systems as linked boundary owners unless behavior evidence makes them part of the module.

## Counterexamples

- Search the full stated scope for counterexamples to dependency direction, uniqueness, absence, completeness, and isolation claims.
- State the searched scope. Label a partial search as representative rather than complete.

Verification is complete when every high-risk ledger claim passes its applicable checks or is a specific unknown, and every owner document reflects that result. For Functional module scope, this includes module identity, reachability, included anchors, boundary edges, and exclusions.
