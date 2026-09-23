function hydrate(raw) {
  return {
    total: raw.total,
    contributions: new Map(Object.entries(raw.contributions || {})),
  }
}

function createScoreStore() {
  const rows = new Map()

  return {
    async increment(guildId, profileId, score) {
      const previous = rows.get(guildId) || { total: 0, contributions: {} }
      const raw = {
        total: previous.total + score,
        contributions: {
          ...previous.contributions,
          [profileId]: (previous.contributions[profileId] || 0) + score,
        },
      }
      rows.set(guildId, raw)
      return hydrate(raw)
    },

    async find(guildId) {
      return hydrate(rows.get(guildId) || { total: 0, contributions: {} })
    },
  }
}

module.exports = { createScoreStore, hydrate }
