import assert from 'node:assert/strict'
import test from 'node:test'

import { loadTasks } from './run-evals.mjs'

test('converts all behavior and trigger evals to Waza tasks', async () => {
  const tasks = await loadTasks()
  const behaviorTasks = tasks.filter((task) => task.tags.includes('behavior'))
  const triggerTasks = tasks.filter((task) => task.tags.includes('trigger'))

  assert.equal(tasks.length, 26)
  assert.equal(behaviorTasks.length, 14)
  assert.equal(triggerTasks.length, 12)
  assert.equal(behaviorTasks[0].inputs.files[0].path, 'evals/files/monorepo.json')
  assert.match(behaviorTasks.at(-1).inputs.prompt, /Use Chinese/)
  assert.match(behaviorTasks.at(-1).inputs.prompt, /top-level "files" object/)
  assert.match(behaviorTasks.at(-1).inputs.prompt, /current working directory/)
  assert.match(behaviorTasks.at(-1).graders[0].config.prompt, /set_waza_grade_pass/)
  assert.match(behaviorTasks.at(-1).graders[0].config.prompt, /README\.md as evidence/)
  assert.equal(triggerTasks[0].graders[0].type, 'trigger')
  assert.equal(triggerTasks.at(-1).expected.should_trigger, false)
})
