import { postInvoice } from "./http-client";

export async function sendInvoice(accountId: string, amount: number) {
  return postInvoice("/invoices", { accountId, amount });
}
