import { expect, test } from "vitest";
import { runSyncJob } from "../src/workers/sync";

test("runs a sync job", () => {
  expect(runSyncJob({ accountId: "acct_1" })).toEqual({
    accountId: "acct_1",
    synced: true,
  });
});
