const assert = require('node:assert/strict')
const test = require('node:test')
const { createApp } = require('../src/app')
const { buildMemberScores } = require('../src/guild/member-view')
const { migrateGuildRegion, recordGuildScore } = require('../src/guild/score-service')

test('reports every positive cumulative total', async () => {
  const reports = []
  await recordGuildScore(
    {
      store: { increment: async () => ({ total: 10 }) },
      leaderboard: { reportTotal: async (...args) => reports.push(args) },
    },
    'g1',
    'p1',
    10
  )
  assert.deepEqual(reports, [['g1', 10]])
})

test('combines roster members and departed contributors from a plain object fixture', () => {
  assert.deepEqual(buildMemberScores(['p1'], { p1: 10, p2: 5 }), [
    { id: 'p1', score: 10 },
    { id: 'p2', score: 5, departed: true },
  ])
})

test('calls report before delete through a stubbed adapter', async () => {
  const calls = []
  const leaderboard = {
    reportTotal: async () => calls.push('report'),
    deleteGuild: async () => calls.push('delete'),
  }
  await migrateGuildRegion({ leaderboard }, 'g1', 10, 'old', 'new')
  assert.deepEqual(calls, ['report', 'delete'])
})

test('composition root reports consecutive cumulative totals after flush', async () => {
  const sent = []
  const app = createApp({ send: async (message) => sent.push(message) })

  await app.settle({ guildId: 'g1', profileId: 'p1', score: 10 })
  await app.settle({ guildId: 'g1', profileId: 'p1', score: 5 })
  assert.deepEqual(sent, [])

  await app.flushLeaderboard()
  assert.deepEqual(sent, [
    { kind: 'report', guildId: 'g1', total: 10, region: undefined },
    { kind: 'report', guildId: 'g1', total: 15, region: undefined },
  ])
})
