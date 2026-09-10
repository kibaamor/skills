import { submitOrder } from "./orders";

export async function handleCheckout(input: { orderId: string; total: number }) {
  return submitOrder(input);
}
