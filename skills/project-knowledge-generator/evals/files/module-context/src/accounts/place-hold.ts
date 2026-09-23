export function placeAccountHold(accountId: string) {
  return { accountId, kind: "account-restriction" as const, status: "blocked" as const };
}
