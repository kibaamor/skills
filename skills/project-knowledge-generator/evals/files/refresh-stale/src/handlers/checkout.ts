export function validateCheckout(input: { sku: string; quantity: number }) {
  if (input.quantity < 1) {
    throw new Error("Quantity must be at least one");
  }

  return { sku: input.sku, quantity: input.quantity };
}
