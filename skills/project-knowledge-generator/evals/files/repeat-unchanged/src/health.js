export function healthStatus() {
  return { status: "ok" };
}

export const routes = new Map([["GET /health", healthStatus]]);
