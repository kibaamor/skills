export async function postInvoice(path: string, body: unknown) {
  return { method: "POST", path, body };
}
