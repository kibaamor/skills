export function enqueueSync(accountId: string) {
  return { accountId, queued: true };
}
