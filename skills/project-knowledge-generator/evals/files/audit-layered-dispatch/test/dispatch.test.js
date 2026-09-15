import assert from "node:assert/strict";
import test from "node:test";
import { onMessage } from "../src/listener.js";

test("dispatch exposes sync, rejects archive, and performs no preview work", () => {
  assert.deepEqual(onMessage({ command: "sync", payload: { workspaceId: "w1" } }), {
    accepted: true,
    result: { workspaceId: "w1", synced: true, syncCount: 1 }
  });
  assert.deepEqual(onMessage({ command: "archive", payload: { workspaceId: "w1" } }), {
    accepted: false,
    reason: "unsupported command"
  });
  assert.deepEqual(onMessage({ command: "preview", payload: { workspaceId: "w1" } }), {
    accepted: true,
    result: undefined
  });
});
