export function placeCheckoutHold(orderId: string) {
  return {
    expiresInMinutes: 15,
    kind: "payment-authorization" as const,
    orderId,
  };
}
