import assert from "node:assert/strict";
import test from "node:test";
import { routes } from "../src/health.js";

test("registered health route returns the service state", () => {
  assert.deepEqual(routes.get("GET /health")(), { status: "ok" });
});
