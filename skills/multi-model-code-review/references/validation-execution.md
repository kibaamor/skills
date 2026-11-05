# Reviewer Command and Validation Policy

## Default: test and verify, but do not modify the reviewed project

Reviewers are allowed and expected to run relevant commands when they materially improve confidence. Do not impose a blanket prohibition on shell commands, scripts, tests, builds, static analyzers, fuzzers, or temporary reproducers. A review that cannot execute a relevant test may still proceed, but must disclose the missing evidence.

The boundary is **non-mutating review**, not command-free review.

## Permitted validation

Subject to a side-effect check, Reviewers may:

- run focused unit, integration, contract, or regression tests;
- run project test scripts and targeted test filters;
- run builds, type checks, linters in check-only mode, static analyzers, race detectors, and sanitizers;
- run bounded fuzz tests or targeted benchmarks when relevant;
- create and execute temporary test programs, reproducer scripts, fixtures, and test inputs in a unique OS temporary directory or verified disposable workspace;
- inspect test code and test output to determine exactly which behavior was exercised.

Reviewers may use shell commands needed for these operations where the host exposes them. Do not assume the absence of a per-child permission argument means commands are unavailable. Use the host's actual available tools and safety boundaries.

## Prohibited without explicit authorization

Do not:

- edit reviewed source files or permanent project tests;
- change tracked project configuration, dependency manifests/lockfiles, generated project assets, or build definitions;
- run formatters/code generators that write into the project;
- mutate Git index, commits, branches, tags, worktrees, or other VCS state;
- install/update/remove packages or dependencies;
- run destructive migrations, delete persistent data, deploy, publish, or modify cloud resources;
- write to production, staging, shared databases/queues/services, or real user data;
- run unbounded load, chaos, or network-scan operations against shared systems.

Prompt instructions are not an operating-system sandbox. If a host cannot prevent a prohibited side effect, the Reviewer must inspect the command and use an isolated alternative or skip it.

## Preflight before a command

1. Identify the exact command, scripts/configuration it invokes, and likely side effects.
2. Prefer the narrowest test that validates the candidate or changed behavior.
3. Check whether it writes to source, permanent tests, config, dependency files, generated assets, VCS state, databases, external services, or caches.
4. Prefer a unique temporary output directory and disposable local services/data.
5. Check for pre-existing artifacts before cleanup; never overwrite or broadly delete them.
6. Bound runtime, CPU, memory, disk, and external requests.
7. Run the command only when the effects are understood and within the allowed boundary.

## Isolation and concurrency

A fresh child context may still share the same workspace. Do not run concurrent commands that would conflict over the same database, port, generated output, test fixture, or cache. Give temporary artifacts unique per-run/per-reviewer directories. Serialize tests that share mutable resources. Reuse a prior test result only when it applies to the same code input and its assertions cover the candidate.

## Temporary scripts

Temporary scripts are allowed. Store them outside the project tree, for example in a unique OS temporary directory. They may read project sources and invoke compilers/test runners with output directed to temporary locations. Do not copy a temporary script into the repository's permanent tests. Document its purpose and exact command.

## Test evidence record

For every executed validation record:

- purpose and hypothesis/candidate;
- exact command/procedure;
- working directory and relevant environment;
- exit code and pass/fail/timeout status;
- concise actual output, especially failing assertion/stack trace;
- test scope and important assertions;
- output/artifact locations;
- observed side effects and confirmation that prohibited project/VCS state was not changed.

Do not claim a test passed based only on its name or a remembered result. Do not generalize beyond exercised paths. A passing test is evidence for its assertions, not proof of broad correctness.

## If execution is unavailable

Continue static investigation. Record the specific command that could not run and why (tool absent, permission denied, environment unavailable, unsafe side effect, timeout, or user authorization needed). Mark a candidate `uncertain`/`not_verifiable` only when the missing runtime evidence materially affects adjudication. Lack of a test alone does not automatically make the overall review PARTIAL.
