# skills

A collection of agent skills. Each skill follows the [Agent Skills](https://agentskills.io) format and is installable with [`npx skills`](https://skills.sh).

## Skills

| Skill | Description |
|---|---|
| `project-knowledge` | Generate or refresh repository knowledge for coding agents (`AGENTS.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `CODE-MAP.md`). Use when documenting or onboarding to a repo, or syncing knowledge after structural changes. |

## Install

Install all skills (agent-agnostic — auto-detects installed coding agents):

```bash
npx skills add kibaamor/skills --all
```

Variants:

```bash
npx skills add kibaamor/skills --list                 # list available skills without installing
npx skills add kibaamor/skills --skill project-knowledge  # install a specific skill
npx skills add kibaamor/skills -g                     # install globally (across projects); project scope is default
```

## Adding a skill

- Each skill lives at `skills/<name>/SKILL.md`.
- `SKILL.md` frontmatter requires `name` (lowercase, hyphens, must equal the directory name) and `description`.
- Optional bundled `references/`, `scripts/`, or `assets/` may be referenced by relative path; they ship with the skill.

## License

MIT — see [LICENSE](LICENSE).
