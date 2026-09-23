const { buildMemberScores } = require('./member-view')

async function recordGuildScore({ store, leaderboard }, guildId, profileId, score) {
  if (score <= 0) return
  const saved = await store.increment(guildId, profileId, score)
  await leaderboard.reportTotal(guildId, saved.total)
}

async function migrateGuildRegion({ leaderboard }, guildId, total, oldRegion, newRegion) {
  await leaderboard.reportTotal(guildId, total, newRegion)
  await leaderboard.deleteGuild(guildId, oldRegion)
}

async function refreshGuild({ leaderboard }, guildId, total, region) {
  await leaderboard.deleteGuild(guildId, region)
  if (total > 0) await leaderboard.reportTotal(guildId, total, region)
  return { score: total }
}

async function getMemberScores({ store }, guildId, memberIds) {
  const saved = await store.find(guildId)
  return buildMemberScores(memberIds, saved.contributions)
}

module.exports = { recordGuildScore, migrateGuildRegion, refreshGuild, getMemberScores }
