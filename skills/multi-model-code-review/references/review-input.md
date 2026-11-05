# Review Input and Baseline Package

## Required evidence

The diff is the primary record of what changed. Current source files alone are not a substitute for a baseline diff.

Prepare one package with:

- `target`: exact requested scope;
- `baseline`: base revision/reference or user-supplied comparison source, when available;
- `change_diff`: complete diff/change content;
- `file_status`: added, modified, deleted, renamed, untracked, or other VCS-native state;
- `changed_files`: all in-scope paths;
- `current_context`: accessible current file content/paths needed to follow the change;
- `baseline_context`: old content for changed/deleted files where useful and available;
- `requirements`: relevant specification, contract, invariant, and acceptance criteria;
- `project_guidance`: relevant instructions/architecture information;
- `tests`: existing tests and prior results relevant to the change;
- `exclusions` and `inaccessible`: what was not reviewed and why.

## VCS-neutral collection

Use the actual VCS's read-only status/diff semantics where present. For Git, collect staged and unstaged changes, and include untracked file contents explicitly. A single `git diff` invocation may omit untracked files. For Perforce/SVN/other systems, use their native pending/opened/working-copy semantics; do not perform workspace-mutating reconciliation just to discover files. With no VCS, use explicit files/directories or supplied before/after content.

Do not require a repository fingerprint or a fixed snapshot mechanism. Record a base identifier when available for attribution. If baseline data is incomplete, continue review when possible but mark introduction attribution `unknown` and disclose that coverage limitation.

## Reviewer instructions

Every Discovery Reviewer receives the same logical diff, file inventory, requirements, and context. The reviewer must inspect the diff first, then inspect current/baseline code needed to understand behavior. It should not review current files as if they alone represented the change. Verification receives the same change package plus candidate evidence and relevant test outputs.

## Context growth

Start from changed files. Read related code only to answer a specific question (caller contract, lifecycle, concurrency, protocol path, persistence, security boundary, or regression test). Record why expanded context was needed. Do not scan unrelated repository areas.
