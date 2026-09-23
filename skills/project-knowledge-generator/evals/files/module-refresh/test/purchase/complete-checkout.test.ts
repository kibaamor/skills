import { expect, test } from "vitest";
import { routes } from "../../src/http/routes";

test("checkout confirms an order", async () => {
  await expect(
    routes["POST /checkout"]({ orderId: "ord_2", total: 40 }),
  ).resolves.toEqual({ orderId: "ord_2", status: "confirmed" });
});
