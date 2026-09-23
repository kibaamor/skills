# Checkout

Checkout turns an accepted HTTP request into a confirmed order result.

Keep route registration separate from orchestration so transport changes do not redefine checkout behavior.

- **Entry point**: `src/http/checkout-route.ts`
- **Orchestration**: `src/checkout/complete.ts`
- **Focused test**: `test/checkout/complete.test.ts`
- **Navigation**: [code map](./CODE-MAP.md)
- **Flow**: [architecture](./ARCHITECTURE.md)
