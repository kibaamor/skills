export function formatDailyTotal(input: { day: string; total: number }) {
  return `${input.day}: ${input.total.toFixed(2)}`;
}
