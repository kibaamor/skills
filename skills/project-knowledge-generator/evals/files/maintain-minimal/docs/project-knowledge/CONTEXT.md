---
id: contact-export.context
summary: Purpose, actors, and current functionality of the contact export service.
source_paths:
  - src/app.js
tests:
  - test/export.test.js
---

# Project Context

The service lets account operators download contacts for offline analysis.

## Functionality

| Capability | Actor or trigger | Caller-visible result | Details |
|---|---|---|---|
| Export contacts | Account operator through POST /exports | CSV with contact identifiers and email addresses | [Account exports](./features/exports.md) |
