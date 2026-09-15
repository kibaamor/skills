export function shouldRetryPayment(attempt: number) {
  return attempt < 3;
}
