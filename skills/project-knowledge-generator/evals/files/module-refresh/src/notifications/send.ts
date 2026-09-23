export async function sendNotification(recipient: string) {
  return { recipient, delivered: true as const };
}
