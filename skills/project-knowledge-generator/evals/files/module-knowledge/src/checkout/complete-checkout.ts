import { reserveStock } from "../inventory/reserve-stock";
import { capturePayment } from "../payments/capture-payment";

export async function completeCheckout(input: {
  orderId: string;
  sku: string;
  total: number;
}) {
  await reserveStock(input.sku);
  const paymentId = await capturePayment(input.orderId, input.total);

  return { orderId: input.orderId, paymentId, status: "confirmed" as const };
}
