const scoreService = require('../guild/score-service')

async function settle(req, dependencies) {
  return scoreService.recordGuildScore(dependencies, req.guildId, req.profileId, req.score)
}

async function members(req, dependencies) {
  return scoreService.getMemberScores(dependencies, req.guildId, req.memberIds)
}

async function migrateGuildRegion(req, dependencies) {
  return scoreService.migrateGuildRegion(
    dependencies,
    req.guildId,
    req.total,
    req.oldRegion,
    req.newRegion
  )
}

async function refreshGuild(req, dependencies) {
  return scoreService.refreshGuild(dependencies, req.guildId, req.total, req.region)
}

module.exports = { settle, members, migrateGuildRegion, refreshGuild }
