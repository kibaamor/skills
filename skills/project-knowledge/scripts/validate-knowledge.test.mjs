import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { validateKnowledge } from './validate-knowledge.mjs'

test('accepts valid knowledge links and heading structure', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'project-knowledge-'))
  await mkdir(path.join(root, 'src'))
  await writeFile(path.join(root, 'src', 'app.js'), 'module.exports = {};\n')
  await writeFile(
    path.join(root, 'AGENTS.md'),
    '# Repository Guide\n\n## Start Here\n\n[App](./src/app.js)\n'
  )

  assert.deepEqual(await validateKnowledge(root, ['AGENTS.md']), [])
})

test('rejects missing links, duplicate headings, and skipped levels', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'project-knowledge-'))
  await writeFile(
    path.join(root, 'CODE-MAP.md'),
    '# Code Map\n\n## Modules\n\n#### Missing\n\n## Modules\n\n[Handler](./src/Handler.js)\n'
  )

  const errors = await validateKnowledge(root, ['CODE-MAP.md'])
  assert.equal(errors.length, 3)
  assert.ok(errors.some((error) => error.includes('heading level skips')))
  assert.ok(errors.some((error) => error.includes('duplicate heading')))
  assert.ok(errors.some((error) => error.includes('unresolved or case-mismatched link')))
})
