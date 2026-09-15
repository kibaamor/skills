---
id: contact-export.architecture
summary: Runtime boundary and request flow for contact exports.
source_paths:
  - src/app.js
tests:
  - test/export.test.js
---

# Architecture

The route registry in src/app.js owns POST /exports and delegates directly to exportContacts. The module has no persistent store or external service.
