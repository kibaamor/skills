export async function reserveStock(sku: string) {
  return { sku, reserved: true as const };
}
