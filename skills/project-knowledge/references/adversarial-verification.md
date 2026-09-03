# Adversarial Verification

Apply these checks to the working evidence ledger.

## Commands

- Trace every documented command through its complete script chain to the final executable.
- Run the narrowest safe invocation when prerequisites are available. A safe invocation does not alter the working tree, write outside a temporary directory, mutate an external system, or make an authenticated network call.
- Record an unverified chain, missing prerequisite, or unsafe invocation as a specific unknown.

## Gated Behavior

- For environment, branch, deployment, security, and feature claims, enumerate configured values and inspect every controlling condition.
- Treat labels such as `production` or `secure` as names, not evidence. Downgrade the claim when any controlling value or condition remains uninspected.

## Domain Definitions

- Confirm cardinality, lifecycle, duration, status, and ownership from behavior-bearing code or focused tests.
- Treat names and prose documentation as leads. When behavior-bearing evidence is incomplete, label the claim as representative or report a specific unknown.

## Counterexamples

- Search the full stated scope for counterexamples to dependency direction, uniqueness, absence, completeness, and isolation claims.
- State the searched scope. Label a partial search as representative rather than complete.

Verification is complete when every high-risk ledger claim passes its applicable checks or is a specific unknown, and every owner document reflects that result.
