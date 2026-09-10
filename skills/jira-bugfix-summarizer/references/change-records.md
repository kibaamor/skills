# Fix Records

Load this file before writing `Fix Records`.

List only effective changed results: landed fix commits, submitted source-control changes, published config or data changes, migrations that ran, or build/deployment/version records that prove where the fix took effect.

Do not list process artifacts as fix records: merge requests, reviews, pipeline runs, draft branches, merge-only commits, temporary branches, or pending changes. You may cite those artifacts only when they contain the authoritative effective record and no better source is available.

If a record proves merge but not deployment, say it landed or merged. If a record proves deployment but not client adoption, say it was deployed and keep client adoption separate.

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

- Use labels like `Config Change`, `Data Change`, `Migration`, `Deployment Version`, `Build Version`, or the project system name.
- Include environment, version, branch, or dataset when needed.
- Link the page showing the effective publication or version result.
