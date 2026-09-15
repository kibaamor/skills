# Static review criteria

Use these criteria for a comprehensive audit or when reviewing a skill's body,
scope, supporting resources, or scripts. For a comprehensive audit, consider
every section. Report material findings and gaps, not the internal checklist.
A criterion is not a mandatory product feature.

## Evidence and added value

- Identify the real expertise behind the skill: completed tasks, user
  corrections, project conventions, schemas, runbooks, failures, or execution
  traces. Generic model knowledge is weak evidence for adding instructions.
- Ask of each instruction: **Would the agent predictably get this wrong without
  it?** If not, remove it or demand behavioral evidence that it earns its
  context cost.
- Prefer corrections supported by observed mistakes. Mark imagined edge cases
  as hypotheses rather than turning them into universal rules.
- Read traces as well as final outputs. Repeated detours can expose vague
  instructions, irrelevant branches, or a menu with no default.

## Scope and interface

- The skill should encapsulate one coherent unit of work. A scope that needs
  several unrelated verbs is likely too broad; a fragment that always requires
  several companion skills may be too narrow.
- The name and folder should be valid, aligned, and useful for discovery.
- The description should route the intended user intent and reject realistic
  adjacent intents. Use the trigger-evaluation reference for a behavioral test.
- Preserve model-invoked versus explicit-only policy unless changing invocation
  is part of the request.

## Information hierarchy

- Keep shared purpose, invariants, routing, and essential workflow in
  `SKILL.md`. Put branch-specific procedures, schemas, and long examples in
  references or assets.
- Every disclosed resource needs a pointer that names the file and the condition
  for reading it. `See references/` is not a usable routing condition.
- Keep one authoritative location for each meaning. Repeated instructions
  inflate their apparent importance and drift independently.
- Treat the 500-line and 5,000-token guidance for `SKILL.md` as review signals,
  not automatic failures. A shorter file can still be bloated; a justified
  complex workflow can be larger.
- Keep non-obvious gotchas in the earliest context where an agent can recognize
  and act on them. Do not require every skill to have a gotchas section.

## Instruction design

- Prefer a reusable procedure over an answer for one task instance.
- Match control to fragility. Explain goals and decision criteria where several
  approaches work; prescribe exact sequences where ordering, safety, or
  consistency makes variation risky.
- Choose a useful default and name an escape hatch when alternatives matter.
  Equal menus make the agent rediscover the choice each run.
- Give ordered steps checkable completion criteria. For multi-step or fragile
  work, a checklist, validation loop, or plan-validate-execute gate may help.
- Use a short template when output shape matters. Keep large or conditional
  templates behind an explicit pointer.
- Prefer positive target behavior. Retain a prohibition only when it protects a
  real guardrail, and pair it with the action the agent should take.

## Scripts

A bundled script is justified when deterministic logic would otherwise be
rewritten across runs. A short pinned one-off tool can stay in `SKILL.md`; a
complex command should become a tested script.

Read the entry point and reachable package-local helpers. Trace how `SKILL.md`
invokes the script and map its inputs, outputs, state changes, network or
credential access, retry behavior, and failure paths before judging its safety
or necessity.

For static script-reference detection, a package-local command in a
shell-language fenced block can count as a script invocation. That exception
affects only script reference recognition. Fenced examples in `SKILL.md` or a
reference file do not make other resources reachable; resource reachability
still requires an instruction-bearing pointer outside the fence.

For each command-line script, check:

- its path is referenced from the skill root and its prerequisites are stated;
- dependencies or one-off tool versions are pinned when reproducibility matters;
- it is non-interactive and accepts input through arguments, environment, or
  stdin;
- concise runtime-appropriate help (`--help`, `-?`, or `/?`) documents inputs,
  examples, and exit meanings;
- invalid input says what failed, what was expected, and what to try;
- stdout contains bounded structured data while diagnostics go to stderr;
- retries are idempotent, ambiguous input is rejected, and stateful or
  destructive work has a dry run and risk-appropriate explicit gate;
- large results default to a summary, pagination, or an explicit output file;
- supported platforms and runtimes match its shell assumptions, path handling,
  executable-bit expectations, encodings, line endings, and external command
  availability. A deliberately platform-specific script should document that
  constraint; portability is not mandatory by itself.

Control false positives by distinguishing capability from reachable behavior.
Imports, API names, strings, and static pattern matches are review leads, not
proof that the documented workflow prompts, mutates state, installs packages,
uses the network, or reads secrets. Ground such findings in an entry point,
reachable branch, or data flow; otherwise label the concern as unverified.

## Safety and authorization

- A skill cannot expand the user's authorization. External writes, messages,
  destructive actions, network access, and credential use still need the same
  scope and approvals as the underlying task.
- Prefer exact resolved targets, previewable plans, isolated output directories,
  and recoverable changes for risky workflows.
- Make stopping conditions proportional to risk. Retries must not become an
  unbounded loop or repeated external mutation.

## Finding quality

A material finding joins evidence to a consequence. Examples:

- `SKILL.md:42` always loads a provider-specific schema, adding context to every
  branch; move it behind a provider-conditioned pointer.
- Three traces each rebuild the same parser and two contain different edge-case
  handling; bundle one tested parser script.
- A validator flags a missing relative file, so the documented workflow cannot
  complete.

Weak findings merely restyle prose, demand every optional pattern, or call the
absence of evidence a demonstrated behavior failure.

## Sources

- [Best practices for skill creators](https://agentskills.io/skill-creation/best-practices)
- [Using scripts in skills](https://agentskills.io/skill-creation/using-scripts)
