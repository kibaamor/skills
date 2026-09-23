import { expect, test } from "vitest";
import { routes } from "../src/http/routes";

test("formats daily totals", () => {
  expect(routes["GET /reports/daily"]({ day: "Monday", total: 12 })).toBe(
    "Monday: 12.00",
  );
});
