export async function completeCheckout(input: { orderId: string; total: number }) {
  if (input.total <= 0) {
    throw new Error("Checkout total must be positive");
  }

  return { orderId: input.orderId, status: "confirmed" as const };
}
