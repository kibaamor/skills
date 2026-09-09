# Repository Instructions

## Agent Skill Authoring

When creating or modifying any agent skill in this repository, follow this section before considering the work complete. Unqualified imperative instructions and the terms `must` and `required` mark completion requirements; `prefer` marks a default; listed signals guide judgment and are not sufficient by themselves.

An explicit user request may override any rule in this section except platform validity requirements and authorization boundaries. In the final response, identify each deviation and explain its rationale. If the request conflicts with platform validity or authorization, explain the conflict and ask for a compatible direction only when one is needed to proceed.

### Scope and Triggering

- Keep each skill focused on one coherent job. Preserve the user's requested scope and authorization boundaries.
- Treat the frontmatter `description` as the skill's routing rule: keep it concise, front-load the primary use case and trigger terms, and add exclusions only when they prevent likely misrouting.
- Include the required `name` and `description` fields. Set the `name` field to a string identical to the skill's parent directory name. Use a short, discoverable `name` containing only lowercase letters, digits, and hyphens; keep it under 64 characters. Prefer an action-oriented name when it improves discovery.
- Preserve supported frontmatter and metadata fields when editing an existing skill.
- For a new skill's OpenAI metadata, leave implicit invocation enabled unless the user explicitly requests an explicit-only skill; express that exception as `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. When editing an existing skill, preserve its current invocation policy unless the user explicitly requests a change. Preserve unrelated `interface`, `policy`, and `dependencies` fields.
- Use current [OpenAI skill guidance](https://developers.openai.com/codex/skills) as the source of truth when changing OpenAI-specific metadata or invocation behavior. If the guidance cannot be retrieved, do not invent or change OpenAI-specific metadata rules; preserve existing OpenAI metadata unchanged and report that the guidance was unavailable.

### Instructions and Structure

- Assume the agent already has general reasoning and coding ability. Include only task-specific knowledge, constraints, decisions, and failure cases that materially change its behavior.
- Describe the required outcome and decision criteria. Use imperative steps with explicit inputs, outputs, and checkable completion criteria when the task has an ordered workflow; specify a fixed sequence only when correctness, safety, permissions, or a fragile operation requires it.
- Prefer positive target behavior. Use prohibitions when they protect safety, correctness, permissions, scope, routing, or a demonstrated failure mode; state the required alternative when one exists.
- Apply progressive disclosure:
  - Keep the shared purpose, essential constraints, common workflow, and routing in `SKILL.md`.
  - Move conditional guidance, schemas, detailed procedures, or examples to focused files under `references/` when doing so avoids loading irrelevant material or makes the entrypoint easier to follow. Keep a simple self-contained skill in one file.
  - Link each reference where it becomes relevant and state the condition for reading it.
- Prefer instructions over scripts. Add a script only when its expected reliability or reuse benefit outweighs its maintenance cost. The following are signals, not automatic triggers:
  - The same logic would otherwise be reimplemented across uses.
  - Executable enforcement is needed to satisfy a defined invariant or output format reliably.
  - An external tool, API operation, or data transformation is more reliable and reusable as executable code.
- Use `assets/` for templates, media, fonts, boilerplate, or other files copied or adapted into generated output, whether selected directly or by a script. Load an asset into context only when the task requires inspecting it.
- For every optional directory or file added or modified by the current task, confirm that the skill workflow, host platform, generated output, a referenced resource, or an executed script uses it; remove unused placeholders introduced by the task.
- Existing-resource removal gate: inspect the resource's callers and purpose, then remove it only when the requested change requires removal and it is within the authorized task scope. Leave unrelated resources unchanged. Report any relevant cleanup opportunity to the user under a distinct `Cleanup suggestions` heading without modifying the resource.
- Keep each fact and rule in one authoritative location. Do not duplicate information that the agent can cheaply inspect from repository files, configuration, commands, or tool help.

### Required Validation

- Re-read the content added or modified by the current task and remove generic advice, stale material, duplicated rules, speculative edge cases, and instructions that do not change behavior. Treat issues in untouched content as observations unless resolving them is necessary for the requested outcome.
- Check that every referenced file exists, every conditional reference says when to read it, and the skill remains usable with the files that will be distributed.
- Resolve each missing reference in this order:
  1. If creating the file is within the authorized scope and preserves the requested behavior, create it.
  2. Otherwise, if removing the reference passes the existing-resource removal gate and preserves the requested behavior, remove it.
  3. If neither action preserves the requested behavior, report the gap to the user.
- Test the `description` against realistic positive, negative, and boundary prompts so that the intended tasks trigger the skill and adjacent tasks do not.
- Discover validation commands from CI configuration, package or task scripts, validation documentation, and the target skill's `README`, `evals/`, and `scripts/`.
- Select local validation checks with this procedure:
  1. Keep only checks that exercise the affected behavior.
  2. Exclude checks with prohibitive risk, runtime, monetary cost, or side effects.
  3. From the remaining checks, run the smallest distinct set that covers the affected behavior.
  4. When more than one remaining check provides the same coverage, prefer the CI-defined command, then a repository task script, validation documentation, and the target skill's files, in that order.
- Run a check that requires production access, external mutation, paid services, credentials, or additional authorization only when it is already authorized and its prerequisites are available.
- If such a check is necessary for completion but is not authorized, request authorization before running it. If it cannot be run, report the exact unrun check and the missing prerequisite.
- If no automated check exercises the changed behavior, state that no applicable automated validation was found.
- Within the available authorization and prerequisites, execute every new or changed script with a representative input and verify its observable result. Otherwise, report the unrun script check and its missing prerequisite.
- Confirm that completion criteria cover the whole requested output and that unavailable facts are surfaced rather than invented.
