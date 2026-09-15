---
id: health-endpoint.architecture
summary: Registration and execution flow for the health endpoint.
source_paths:
  - src/health.js
tests:
  - test/health.test.js
---

# Architecture

The route registry in src/health.js maps GET /health directly to healthStatus. The function reads no store, calls no external system, and returns the current process status.
