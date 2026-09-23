function createHostedLeaderboard(transport) {
  const pendingReports = []

  return {
    async reportTotal(guildId, total, region) {
      pendingReports.push({ guildId, total, region })
      return { queued: true }
    },

    async deleteGuild(guildId, region) {
      try {
        return await transport.send({ kind: 'delete', guildId, region })
      } catch {
        return null
      }
    },

    async flush() {
      const reports = pendingReports.splice(0)
      return Promise.all(reports.map((report) => transport.send({ kind: 'report', ...report })))
    },
  }
}

module.exports = { createHostedLeaderboard }
