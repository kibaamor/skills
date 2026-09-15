import assert from "node:assert/strict";
import test from "node:test";
import { routes } from "../src/app.js";
import { eventConsumers } from "../src/events.js";
import { scheduledJobs } from "../src/jobs.js";

test("registered order route exposes success and validation failure", async () => {
  const handle = routes.get("POST /orders");
  assert.deepEqual(await handle({ id: "ord-1", total: 25 }), {
    status: 201,
    body: { id: "ord-1", status: "submitted" }
  });
  assert.equal((await handle({ id: "ord-2", total: 0 })).status, 400);
});

test("registered hourly job expires only overdue pending orders", () => {
  const job = scheduledJobs.get("expire-pending-orders");
  assert.equal(job.schedule, "0 * * * *");
  const orders = [
    { id: "ord-1", status: "pending", expiresAt: 10 },
    { id: "ord-2", status: "paid", expiresAt: 10 },
    { id: "ord-3", status: "pending", expiresAt: 30 }
  ];
  assert.deepEqual(job.run(orders, 20), { expired: 1 });
  assert.deepEqual(orders.map((order) => order.status), ["expired", "paid", "pending"]);
});

test("registered payment consumer changes matching order state", () => {
  const consume = eventConsumers.get("payment.captured");
  const orders = [{ id: "ord-1", status: "submitted" }];
  assert.deepEqual(consume({ orderId: "ord-1" }, orders), {
    orderId: "ord-1",
    status: "paid"
  });
  assert.equal(orders[0].status, "paid");
  assert.throws(() => consume({ orderId: "missing" }, orders), /order not found/);
});
