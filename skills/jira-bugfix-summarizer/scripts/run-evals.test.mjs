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
      /no client update required/.test(task.inputs.prompt),
    ),
  );
  assert.ok(
    behaviorTasks.some((task) =>
      /I do not know the final landed commit/.test(task.inputs.prompt),
    ),
  );
  assert.ok(
    behaviorTasks.some((task) =>
      /requires Android app 6\.20\.2/.test(task.inputs.prompt),
    ),
  );
  assert.match(
    behaviorTasks[0].graders[0].config.prompt,
    /must not submit, comment on, or write to Jira/,
  );
  assert.match(
    behaviorTasks[1].graders[0].config.prompt,
    /asking for the missing record is the correct completed task/,
  );
  assert.equal(behaviorTasks[0].expected.should_trigger, true);
  assert.equal(triggerTasks[0].graders[0].type, "trigger");
  assert.equal(triggerTasks[0].expected.should_trigger, true);
  assert.equal(triggerTasks.at(-1).expected.should_trigger, false);
});
