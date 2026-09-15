---
id: health-endpoint.context
summary: Purpose and current functionality of the health endpoint package.
source_paths:
  - src/health.js
tests:
  - test/health.test.js
---

# Project Context

The package lets operators inspect the process health state.

## Functionality

| Capability | Actor or trigger | Caller-visible result | Implementation and tests |
|---|---|---|---|
| Inspect health | Operator calls GET /health | status is ok | src/health.js healthStatus; test/health.test.js |
