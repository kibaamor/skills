import { expect, test } from "vitest";
import { shouldRetryPayment } from "../src/retry";

test("retries only before the third attempt", () => {
  expect(shouldRetryPayment(1)).toBe(true);
  expect(shouldRetryPayment(3)).toBe(false);
});
