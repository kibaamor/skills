export function expirePendingOrders(orders, now) {
  let expired = 0;
  for (const order of orders) {
    if (order.status === "pending" && order.expiresAt <= now) {
      order.status = "expired";
      expired += 1;
    }
  }
  return { expired };
}

export const scheduledJobs = new Map([
  ["expire-pending-orders", {
    schedule: "0 * * * *",
    run: expirePendingOrders
  }]
]);
