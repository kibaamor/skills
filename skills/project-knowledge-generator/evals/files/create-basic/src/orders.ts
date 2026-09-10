export async function submitOrder(input: { orderId: string; total: number }) {
  if (input.total <= 0) {
    throw new Error("Order total must be positive");
  }

  return { id: input.orderId, status: "submitted" as const };
}
