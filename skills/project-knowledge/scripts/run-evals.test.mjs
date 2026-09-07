import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { loadTasks } from "./run-evals.mjs";

test("converts all behavior and trigger evals to Waza tasks", async () => {
  const behaviorConfig = JSON.parse(
    await readFile(new URL("../evals/evals.json", import.meta.url)),
  );
  const triggerConfig = JSON.parse(
    await readFile(new URL("../evals/trigger-evals.json", import.meta.url)),
  );
  const tasks = await loadTasks();
  const behaviorTasks = tasks.filter((task) => task.tags.includes("behavior"));
  const triggerTasks = tasks.filter((task) => task.tags.includes("trigger"));

  assert.equal(
    tasks.length,
    behaviorConfig.evals.length + triggerConfig.length,
  );
  assert.equal(behaviorTasks.length, behaviorConfig.evals.length);
  assert.equal(triggerTasks.length, triggerConfig.length);
  assert.equal(new Set(tasks.map((task) => task.id)).size, tasks.length);
  assert.ok(
    behaviorTasks.some((task) =>
      /competing prose names/.test(task.inputs.prompt),
    ),
  );
  assert.ok(
    behaviorTasks.some((task) => /rename detection/.test(task.inputs.prompt)),
  );
  assert.ok(
    behaviorTasks.some((task) => /non-JavaScript/.test(task.inputs.prompt)),
  );
  assert.match(behaviorTasks.at(-1).inputs.prompt, /top-level "files" object/);
  assert.match(behaviorTasks.at(-1).inputs.prompt, /current working directory/);
  assert.match(behaviorTasks.at(-1).inputs.prompt, /```json/);
  assert.match(behaviorTasks.at(-1).inputs.prompt, /"files"/);
  assert.match(behaviorTasks.at(-1).inputs.prompt, /pytest>=8/);
  assert.match(behaviorTasks.at(-1).inputs.prompt, /python -m pytest/);
  assert.equal(behaviorTasks.at(-1).inputs.files, undefined);
  assert.match(
    behaviorTasks.at(-1).graders[0].config.prompt,
    /set_waza_grade_pass/,
  );
  assert.match(
    behaviorTasks.at(-1).graders[0].config.prompt,
    /README\.md as evidence/,
  );
  assert.equal(triggerTasks[0].graders[0].type, "trigger");
  assert.equal(triggerTasks.at(-1).expected.should_trigger, false);
});
