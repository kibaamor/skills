# Agent Skills

This repository contains reusable [Agent Skills](https://agentskills.io) that can be installed with [`npx skills`](https://skills.sh).

## Available Skills

| Skill | Use it when | Do not use it for |
| --- | --- | --- |
| `jira-bugfix-summarizer` | Summarizing an already fixed Jira bug for stakeholders, including impact, root cause, fix, validation, and effective fix records. | Diagnosing unresolved bugs, implementing fixes, or updating Jira. |
| `project-knowledge-generator` | Creating, regenerating, refreshing, or syncing repository-wide knowledge docs for coding agents, including `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, `ARCHITECTURE.md`, `CODE-MAP.md`, and ADRs. | Explain-only repo walkthroughs or localized edits to one existing document. |
| `skill-reviewer` | Reviewing, auditing, evaluating, or improving an existing agent skill, including activation scope, progressive disclosure, references, scripts, and observed behavior. | Ordinary code review, creating a skill from scratch, installing skills, or tuning prompts that are not agent skills. |

## Installation

List available skills without installing anything:

```bash
npx skills@latest add kibaamor/skills --list
```

Install every skill in this repository:

```bash
npx skills@latest add kibaamor/skills --all
```

Install a single skill:

```bash
npx skills@latest add kibaamor/skills --skill jira-bugfix-summarizer
npx skills@latest add kibaamor/skills --skill project-knowledge-generator
npx skills@latest add kibaamor/skills --skill skill-reviewer
```

## Repository Layout

```text
skills/
  <skill-name>/
    SKILL.md       # required skill definition and instructions
    agents/        # optional client-specific metadata
    references/    # optional supporting docs loaded on demand
    scripts/       # optional helper scripts bundled with the skill
    assets/        # optional static assets bundled with the skill
    evals/         # optional evaluation fixtures and cases
```

Each published skill lives in `skills/<name>/SKILL.md`. Example skills used only as evaluation fixtures live under an `evals/` directory and are not top-level install targets.

## Troubleshooting

### Global install reports a PromptScript error

If a global install prints `github-copilot Agent detected — installing
non-interactively` and then fails with `PromptScript does not support global
skill installation`, run the command with Copilot environment variables unset:

```bash
env -u COPILOT_MODEL -u COPILOT_GITHUB_TOKEN npx skills@latest add kibaamor/skills -g
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for repository
conventions, skill authoring guidance, validation steps, and pull request
expectations.

## License

MIT - see [LICENSE](LICENSE).
