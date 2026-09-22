---
name: trigger-lean-skill
description: Use this skill when the user explicitly asks to run the Acme deployment pipeline. Do not use it for infrastructure changes, local builds, or credential rotation.
---

# Acme Deployment

1. Confirm the release notes are attached to the deployment ticket.
2. Run `acme deploy --prod` and report the resulting pipeline URL.
