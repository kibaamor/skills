export const MAX_EXPORT_ROWS = 1000;

export function exportContacts(rows) {
  if (rows.length > MAX_EXPORT_ROWS) {
    throw new Error("export row limit exceeded");
  }
  return ["id,email", ...rows.map((row) => row.id + "," + row.email)].join("\n");
}

export const routes = new Map([["POST /exports", exportContacts]]);
