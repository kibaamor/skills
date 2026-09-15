export async function submitOrder(input) {
  if (input.total <= 0) {
    throw new Error("total must be positive");
  }
  return { id: input.id, status: "submitted" };
}

export const routes = new Map([
  ["POST /orders", async (input) => {
    try {
      return { status: 201, body: await submitOrder(input) };
    } catch (error) {
      return { status: 400, body: { error: error.message } };
    }
  }]
]);
