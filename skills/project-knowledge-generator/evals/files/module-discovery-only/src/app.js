const routes = require('./http/routes')
const { createScoreStore } = require('./guild/score-store')
const { createHostedLeaderboard } = require('./platform/hosted-leaderboard')

function createApp(transport) {
  const leaderboard = createHostedLeaderboard(transport)
  const dependencies = {
    store: createScoreStore(),
    leaderboard,
  }

  return {
    settle: (req) => routes.settle(req, dependencies),
    members: (req) => routes.members(req, dependencies),
    migrateGuildRegion: (req) => routes.migrateGuildRegion(req, dependencies),
    refreshGuild: (req) => routes.refreshGuild(req, dependencies),
    flushLeaderboard: () => leaderboard.flush(),
  }
}

module.exports = { createApp }
