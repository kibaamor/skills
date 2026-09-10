import { expect, test } from "vitest";
import { sendInvoice } from "../src/billing";

test("sends invoice through HTTP", async () => {
  await expect(sendInvoice("acct_1", 25)).resolves.toMatchObject({
    method: "POST",
    path: "/invoices",
  });
});
