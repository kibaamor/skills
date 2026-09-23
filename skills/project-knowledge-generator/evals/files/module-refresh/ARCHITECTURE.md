# Architecture

Notification delivery is a repository-level shared concern.

Checkout turns an accepted HTTP request into a confirmed order. The checkout route calls `src/checkout/complete.ts` to perform that flow.
