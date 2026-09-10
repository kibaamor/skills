export function runSyncJob(job: { accountId: string }) {
  return { accountId: job.accountId, synced: true };
}
