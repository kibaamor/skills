import { expect, test } from "vitest";
import { validateCheckout } from "../src/handlers/checkout";

test("rejects zero quantity", () => {
  expect(() => validateCheckout({ sku: "sku_1", quantity: 0 })).toThrow(
    "Quantity must be at least one",
  );
});
