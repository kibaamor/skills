import { expect, test } from "vitest";
import { formatDailyTotal } from "../src/reporting";

test("formats daily totals", () => {
  expect(formatDailyTotal({ day: "Monday", total: 12 })).toBe("Monday: 12.00");
});
