---
name: focused-skill
description: Use this skill when an operator asks to recover the Acme queue consumer after a documented LEASE_STALE failure. Do not use it for general queue debugging or undeclared failure codes.
---

# Acme Consumer Recovery

Confirm that the observed failure code is `LEASE_STALE`, then read
[references/recovery.md](references/recovery.md) and follow its verified
recovery sequence. Stop and report the observed code for any other failure.
