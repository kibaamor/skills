---
id: workspace-socket.context
summary: Actors and supported workspace command functionality.
source_paths:
  - src/listener.js
  - src/dispatcher.js
  - src/handlers.js
tests:
  - test/dispatch.test.js
---

# Project Context

Socket clients send workspace commands to synchronize, preview, or archive a workspace.

## Functionality

| Capability | Trigger | Documented caller-visible result |
|---|---|---|
| Synchronize workspace | sync command | Confirmation containing synced: true |
| Preview workspace | preview command | A generated workspace preview |
| Archive workspace | archive command | Confirmation containing archived: true |
