import { previewWorkspace, syncWorkspace } from "./handlers.js";

const commandHandlers = new Map([
  ["sync", syncWorkspace],
  ["preview", previewWorkspace]
]);

export function dispatch(command, payload) {
  return commandHandlers.get(command)(payload);
}
