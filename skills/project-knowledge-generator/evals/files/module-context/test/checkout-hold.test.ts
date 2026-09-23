import { expect, test } from "vitest";
import { routes } from "../src/http/routes";

test("checkout creates an expiring payment authorization", () => {
  expect(routes["POST /checkout/hold"]("ord_3")).toEqual({
    expiresInMinutes: 15,
    kind: "payment-authorization",
    orderId: "ord_3",
  });
});
