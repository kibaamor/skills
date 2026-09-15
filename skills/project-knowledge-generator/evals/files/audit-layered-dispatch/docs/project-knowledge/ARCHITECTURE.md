---
id: workspace-socket.architecture
summary: Listener, command routing, and handler boundaries for workspace commands.
source_paths:
  - src/listener.js
  - src/dispatcher.js
  - src/handlers.js
tests:
  - test/dispatch.test.js
---

# Architecture

External messages enter onMessage in src/listener.js. Accepted commands pass to dispatch in src/dispatcher.js, which selects a function from the command map and invokes the handler in src/handlers.js.
