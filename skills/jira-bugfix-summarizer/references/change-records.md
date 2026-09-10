# Fix Records

Load this file before writing `Fix Records`.

List only effective changed results: landed fix commits, submitted source-control changes, published config/data changes, or build/deployment/version records that prove where the fix took effect.

Do not list process artifacts: merge requests, reviews, pipeline runs, draft branches, merge-only commits, temporary branches, or pending changes.

## Format

```markdown
- `<Source> <branch/environment/scope>`: [`<display ID>`](<authoritative URL>) - `<functional change>`
```

If no effective record is available, ask for the final commit/change/config/data/build/deployment record. Continue without one only after explicit approval; then write `No effective fix record is available to cite`.

## Git

- Display short SHA; link full SHA.
- GitLab: `<base-url>/-/commit/<full-sha>`.
- GitHub: `<base-url>/commit/<full-sha>`.
- Derive HTTPS base URL from remote when possible, such as `git@gitlab.example.com:group/project.git` -> `https://gitlab.example.com/group/project`.

## Centralized Source Control

- Use submitted official change IDs only.
- Include branch, stream, depot path, or workspace label when needed.
- Link the authoritative change detail page.

## Other Sources

- Use labels like `Config Change`, `Data Change`, `Deployment Version`, `Build Version`, or the project system name.
- Include environment, version, branch, or dataset when needed.
- Link the page showing the effective publication or version result.
