import { expect, test } from "vitest";
import { submitOrder } from "../src/orders";

test("submits positive orders", async () => {
  await expect(submitOrder({ orderId: "ord_1", total: 10 })).resolves.toEqual({
    id: "ord_1",
    status: "submitted",
  });
});
