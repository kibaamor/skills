import { expect, test } from "vitest";
import { routes } from "../src/http/routes";

test("checkout confirms a paid order", async () => {
  await expect(
    routes["POST /checkout"]({ orderId: "ord_1", sku: "sku_1", total: 25 }),
  ).resolves.toEqual({
    orderId: "ord_1",
    paymentId: "pay_ord_1",
    status: "confirmed",
  });
});
