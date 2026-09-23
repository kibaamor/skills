function buildMemberScores(memberIds, contributions) {
  const members = memberIds.map((id) => ({ id, score: contributions[id] || 0 }))
  for (const id of Object.keys(contributions)) {
    if (!memberIds.includes(id)) members.push({ id, score: contributions[id], departed: true })
  }
  return members
}

module.exports = { buildMemberScores }
