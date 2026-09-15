import assert from "node:assert/strict";
import test from "node:test";
import { exportContacts, MAX_EXPORT_ROWS } from "../src/app.js";

test("exports stable columns up to the current limit", () => {
  assert.equal(MAX_EXPORT_ROWS, 1000);
  assert.equal(exportContacts([{ id: "c1", email: "a@example.test" }]), "id,email\nc1,a@example.test");
  assert.throws(() => exportContacts(new Array(1001).fill({ id: "c", email: "a@example.test" })));
});
