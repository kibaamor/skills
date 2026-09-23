export async function capturePayment(orderId: string, total: number) {
  if (total <= 0) {
    throw new Error("Payment total must be positive");
  }

  return `pay_${orderId}`;
}
