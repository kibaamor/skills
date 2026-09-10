# Skills

Agent skills in the [Agent Skills](https://agentskills.io) format, installable with [`npx skills`](https://skills.sh).

## Skills

| Skill | Description |
| --- | --- |
| `jira-bugfix-summarizer` | Summarize an already fixed Jira bug for stakeholders, covering impact, root cause, fix, validation, and effective fix records; not for diagnosis, implementation, or Jira updates. |
| `project-knowledge-generator` | Generate or refresh repository knowledge docs for coding agents (`AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, `CODE-MAP.md`, ADRs). Use for onboarding, full regeneration, structural-change sync, or CODE-MAP-only refresh; not for localized edits to one existing doc. |
| `skill-reviewer` | Review and improve agent skills against skill-creation best practices, including activation scope, concrete expertise, calibrated control, validation loops, and progressive disclosure. |

## Install

Install every skill in this repository:

```bash
npx skills@latest add kibaamor/skills --all
```

Variants:

```bash
npx skills@latest add kibaamor/skills --list                 # list available skills without installing
npx skills@latest add kibaamor/skills --skill jira-bugfix-summarizer       # install a specific skill
npx skills@latest add kibaamor/skills --skill project-knowledge-generator  # install a specific skill
npx skills@latest add kibaamor/skills --skill skill-reviewer               # install a specific skill
```

## Troubleshooting

### Global install reports a PromptScript error

If a global install prints `github-copilot Agent detected — installing
non-interactively` and then fails with `PromptScript does not support global
skill installation`, run the command with Copilot environment variables unset:

```bash
env -u COPILOT_MODEL -u COPILOT_GITHUB_TOKEN npx skills@latest add kibaamor/skills -g
```

## Contributing a skill

- Each skill lives at `skills/<name>/SKILL.md`.
- `SKILL.md` frontmatter requires `name` (lowercase, hyphens, must equal the directory name) and `description`.
- Optional bundled `references/`, `scripts/`, or `assets/` may be referenced by relative path; they ship with the skill.

## License

MIT — see [LICENSE](LICENSE).
