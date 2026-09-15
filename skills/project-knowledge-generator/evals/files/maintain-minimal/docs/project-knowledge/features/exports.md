---
id: contact-export.exports
summary: Export limits, file shape, and verification route.
read_when:
  - Changing export limits or CSV columns.
source_paths:
  - src/app.js
source_symbols:
  - exportContacts
  - MAX_EXPORT_ROWS
tests:
  - test/export.test.js
---

# Account exports

Human-maintained note: Keep the id,email column order stable because partner imports compare headers.

POST /exports accepts at most 500 contacts and returns one CSV row per contact. Larger requests fail with export row limit exceeded.

Verify the boundary and column order with test/export.test.js.
