import { formatDailyTotal } from "../reporting";

export const routes = {
  "GET /reports/daily": formatDailyTotal,
};
