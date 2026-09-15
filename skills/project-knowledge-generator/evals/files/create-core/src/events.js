export function applyPaymentCaptured(event, orders) {
  const order = orders.find((candidate) => candidate.id === event.orderId);
  if (!order) {
    throw new Error("order not found");
  }
  order.status = "paid";
  return { orderId: order.id, status: order.status };
}

export const eventConsumers = new Map([
  ["payment.captured", applyPaymentCaptured]
]);
