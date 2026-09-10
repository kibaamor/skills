# Fix Records

`Fix Records` must list only effective changed results. For each record, state the source, branch or scope, display ID, URL, and functional change description; do not expand implementation diffs.

## General Format

```markdown
- `<Source/system> <branch/environment>`: [`<display ID>`](<URL showing the effective changed result>) - `<functional change description>`
```

The source can be a landed Git commit containing the fix diff, a submitted source-control change record, a published config record, an effective data record, or a deployment/build version page that confirms where the fix took effect. Omit record types that do not exist.

Do not list process records in `Fix Records`, such as merge requests, reviews, temporary branches, draft changes, merge commits that only represent merge activity, pipeline runs, or unlanded pending changes. They can only be used as clues for finding the final effective result. If no fix record information is available, or only process records are available, ask the user to confirm the final effective commit, source-control change record, config publication, data effectuation, or deployment/build version record. Proceed without one only after the user explicitly agrees; in that case, do not list process records as substitutes.

When the user explicitly agrees to continue without an effective fix record, write `No effective fix record is available to cite` in `Fix Records` and state that the effective fix record could not be confirmed.

## Git

- Prefer deriving the base URL from the Git remote. An SSH remote such as `git@gitlab.example.com:group/project.git` maps to `https://gitlab.example.com/group/project`.
- For GitLab, use commit URL format `<base-url>/-/commit/<full-sha>`. For GitHub, use `<base-url>/commit/<full-sha>`. For other providers, use a user-supplied or provider-specific authoritative commit URL.
- Use the short SHA as display text and the full SHA in the link.
- List only commits that have landed in the target branch or deployed version and contain the fix diff.
- Do not list commits that only represent merge activity, review flow, or temporary synchronization.

## Centralized Source Control

- List only submitted source-control change records, written with their official change ID.
- Include the branch, stream, depot path, or workspace label when it helps identify where the change landed.
- Link each change ID to the authoritative change detail page instead of only providing local command output.

## Other Sources

- Use clear source labels, such as `Config Change`, `Data Change`, `Deployment Version`, `Build Version`, or the project-specific system name.
- Include the branch, environment, version, or dataset when it helps identify the change scope.
- Link to pages that show the effective changed result, publication result, or build version result.
