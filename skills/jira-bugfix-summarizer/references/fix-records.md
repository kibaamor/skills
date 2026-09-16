# Fix Records

Use this file whenever drafting the default `Fix Records` section loaded through workflow step 4.

The section must first explain how the issue was fixed, then list the actual modification records that make the fix traceable. List only final effective changed results: landed fix commits, submitted source-control changes, published config or data changes, migrations that ran, or build/deployment/version records that prove where the fix took effect.

Do not list process or intermediate repair artifacts as fix records: merge requests, reviews, pipeline runs, draft branches, merge-only commits, temporary branches, superseded commits, reverted attempts, partial fixes, investigation notes, or pending changes. You may cite those artifacts only when they contain the authoritative effective record and no better source is available.

When several records describe the same fix, choose the latest record that proves the fix became effective. Prefer deployment, build version, release version, published config/data, or completed migration records when they prove runtime effect. Use landed commits or submitted changes only when no later effective publication record is available. If code plus config, data, migration, or client release records are all required for the fix to work, list each required final record once.

If a record proves merge but not deployment, say it landed or merged. If a record proves deployment but not client adoption, say it was deployed and keep client adoption separate.

## Format

```markdown
<One short paragraph explaining how the issue was fixed, the new behavior, and any required user or customer action.>

- `<Source> <branch/environment/scope>`: [`<display ID>`](<authoritative URL that shows the actual changes>) - `<functional change>`
```

Every listed modification record must be a Markdown link to an authoritative URL where a reader can view the actual changes. Prefer the web UI for the repository, change system, build, deployment, release, configuration, data, or migration record. Do not use local filesystem paths, raw pasted diffs, or unlinked identifiers as the record link.

If no final effective record or URL showing the actual changes is available, ask for the final commit/change/config/data/build/deployment record and its viewable address. Continue without one only after explicit approval; then write `No effective fix record is available to cite`.

## Git

- Display short SHA; link to the repository web commit page for the full SHA, so the reader can inspect the actual diff.
- GitLab: `<base-url>/-/commit/<full-sha>`.
- GitHub: `<base-url>/commit/<full-sha>`.
- Derive HTTPS base URL from remote when possible, such as `git@gitlab.example.com:group/project.git` -> `https://gitlab.example.com/group/project`. If the repository web base URL cannot be derived, ask for it instead of listing an unlinked SHA.

## Centralized Source Control

- Use submitted official change IDs only.
- Include branch, stream, depot path, or workspace label when needed.
- Link the authoritative change detail page that shows the actual submitted modifications.

## Other Sources

- Use labels like `Config Change`, `Data Change`, `Migration`, `Deployment Version`, `Build Version`, or the project system name.
- Include environment, version, branch, or dataset when needed.
- Link the page showing the effective publication or version result.
