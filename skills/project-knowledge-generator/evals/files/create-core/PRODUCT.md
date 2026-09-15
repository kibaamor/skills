# Tiny Orders

Tiny Orders lets storefront clients submit purchase orders over HTTP. A valid positive total produces a submitted order; a non-positive total is rejected.

An hourly scheduled job expires pending orders whose deadline has passed. The payment integration also publishes `payment.captured` events; the registered consumer marks the matching submitted order as paid and rejects events for unknown orders.
