let syncCount = 0;

export function syncWorkspace(payload) {
  syncCount += 1;
  return { workspaceId: payload.workspaceId, synced: true, syncCount };
}

export function previewWorkspace() {
  return undefined;
}

export function archiveWorkspace(payload) {
  return { workspaceId: payload.workspaceId, archived: true };
}
