import { dispatch } from "./dispatcher.js";

const allowedCommands = new Set(["sync", "preview"]);

export function onMessage(message) {
  if (!allowedCommands.has(message.command)) {
    return { accepted: false, reason: "unsupported command" };
  }
  return { accepted: true, result: dispatch(message.command, message.payload) };
}
