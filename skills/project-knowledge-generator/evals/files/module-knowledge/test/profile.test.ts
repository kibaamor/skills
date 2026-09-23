import { expect, test } from "vitest";
import { routes } from "../src/http/routes";

test("trims a profile display name", () => {
  expect(routes["POST /profile/display-name"]("  Ada  ")).toEqual({
    displayName: "Ada",
  });
});
