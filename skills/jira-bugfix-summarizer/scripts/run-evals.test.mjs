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
  assert.ok(
    behaviorTasks.some((task) =>
      /订单备注保存后列表未刷新/.test(task.inputs.prompt),
    ),
  );
  assert.ok(
    behaviorTasks.some((task) =>
      /通知开关关闭后仍发送提醒/.test(task.inputs.prompt),
    ),
  );
  assert.ok(
    behaviorTasks.some((task) =>
      /账单状态更新后仍显示处理中/.test(task.inputs.prompt),
    ),
  );
  assert.match(
    behaviorTasks[0].graders[0].config.prompt,
    /must not create, update, edit, submit, comment on, or write to Jira, external systems, files, repositories, or any other resource/,
  );
  assert.match(
    behaviorTasks[1].graders[0].config.prompt,
    /unless the prompt says the user explicitly agrees to continue without one/,
  );
  assert.equal(behaviorTasks[0].expected.should_trigger, true);
  assert.equal(triggerTasks[0].graders[0].type, "trigger");
  assert.equal(triggerTasks[0].expected.should_trigger, true);
  assert.ok(
    triggerTasks.some((task) =>
      /Jira comment and post it to Slack/.test(task.inputs.prompt),
    ),
  );
  assert.ok(
    triggerTasks.some((task) =>
      /update the release notes file/.test(task.inputs.prompt),
    ),
  );
  assert.equal(triggerTasks.at(-1).expected.should_trigger, false);
});
