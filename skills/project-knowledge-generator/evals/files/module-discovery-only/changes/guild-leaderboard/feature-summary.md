# Guild leaderboard delivery summary

This file is a temporary delivery handoff and will be deleted after durable agent knowledge is generated. The final knowledge base must not name or link it.

The guild leaderboard accumulates every positive settled score and reports the cumulative guild total. Scores below 500 are filtered on the server. A monthly board is planned after launch.

The hosted board is configured outside this repository to retain the maximum score. Cumulative reports were chosen so a later settlement can converge after a failed report without a reconciliation job. Region migration reports the new region before deleting the old one to avoid a visibility gap and preserve shared regions.

Stored contribution maps hydrate as plain objects, so the member view can use property access and `Object.keys`.
