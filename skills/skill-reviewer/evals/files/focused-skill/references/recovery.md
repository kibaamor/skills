# LEASE_STALE recovery

1. Run `acme-consumer inspect --format json` and save the lease identifier.
2. Run `acme-consumer recover --lease ID --dry-run`.
3. Continue only when the dry run names the same lease identifier.
4. Run `acme-consumer recover --lease ID --confirm` and verify the consumer is
   healthy with `acme-consumer status --format json`.
