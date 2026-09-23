# Architecture

HTTP registrations share one in-process route map in `src/http/routes.ts`.

The profile area owns customer display-name changes. Its internal flow is unrelated to checkout.
