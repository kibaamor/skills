# Domain Review Guidance

Use only the sections relevant to changed code. Convert the knowledge into concrete checks; do not paste generic expertise lists into reviewer prompts.

## Common engineering checks

- **Requirements/contracts:** for each binding requirement identify the changed path, expected behavior, evidence, and any uncovered case.
- **Correctness:** trace real control/data flow, boundary values, state transitions, default values, error handling, retries, partial operations, and compatibility.
- **Ownership/lifecycle:** inspect creation, completion, failure, cancellation, timeout, cleanup, and shutdown paths for leaks, use-after-free, stale callbacks, or premature release.
- **Concurrency:** name actors, shared state, synchronization, concrete interleaving, and impact. Avoid hypothetical race claims.
- **Security:** state attacker capability, trust boundary, preconditions, reachable path, affected asset, and impact.
- **Performance/reliability:** identify hot path, cost/complexity, scale assumption, resource bound, backpressure, and failure mode.
- **Architecture/maintainability:** report material coupling, unclear ownership, fragile abstractions, or change amplification—not personal style.
- **Tests:** inspect assertions and exercised paths. Check failure, boundary, concurrency, compatibility, and regression behavior. Do not infer historical TDD order from final files.
- **Alternatives:** compare the current approach with a concrete feasible alternative, net benefit, implementation cost, migration risk, and project fit.

## Network/protocol systems

For HTTP/proxy/streaming changes, inspect only relevant paths:

- HTTP/1.1 message framing, Content-Length vs Transfer-Encoding, connection-specific headers, Connection nominations, trailer declaration/collection/forwarding, partial reads/writes, informational responses, CONNECT, upgrades, keep-alive/reuse;
- HTTP/2 frame and stream state, END_STREAM, RST_STREAM, flow control, header/trailer ordering, pseudo-header rules, stream cancellation and connection reuse;
- gRPC framing, metadata, status/trailers, cancellation, half-close and error propagation;
- proxy conversion semantics, hop-by-hop behavior, authority/path handling, header normalization and state isolation.

For any ignored read/write error, trace whether partial data can reach hooks, parsers, trailer collection, transaction commit, or downstream forwarding. Verify error propagation and cleanup with focused tests where feasible.

## Go

Inspect `io.Reader`/`io.Writer` contracts (including partial data plus non-nil error), `net/http` request/response body closure, trailer availability, Transport connection reuse, goroutine cancellation/leaks, contexts, mutex/atomic synchronization, error wrapping, race conditions, and test/race-detector coverage. Do not infer that `io.ReadAll` or a custom reader cannot return partial data with an error.

## Modern C++

Inspect RAII, object lifetime, ownership, references/views/iterators, move semantics, exception safety, undefined behavior, data races/memory ordering, lock ordering, callback captures, allocator/container invalidation, ABI/ODR, and sanitizer coverage.

## C#/.NET

Inspect async/await, cancellation propagation, sync-over-async, Task lifecycle, synchronization context/thread pool behavior, IDisposable/IAsyncDisposable, DI lifetimes, exceptions, nullable boundaries, serialization, and allocation/performance on relevant paths.

## JavaScript/TypeScript/Node.js

Inspect event-loop and microtask behavior, Promise rejection handling, async cancellation, stream backpressure, worker/shared state, runtime validation (types are erased), module state, event listener lifecycle, and resource cleanup.

## Databases and distributed systems

Inspect transaction boundaries/isolation, unique constraints and concurrent upsert races, retry/idempotency, ordering, acknowledgements, outbox/inbox, schema migration compatibility, indexes/query plans, cache source-of-truth/invalidation, partial failure and recovery.

## Game engines and online services

For UE/Unity changes, inspect object/Actor/component lifecycle, GC/serialization, thread affinity, delegates/timers/async callbacks, module/plugin loading, replication/authority, asset/build/platform constraints. For game backend changes inspect server authority, account/session lifecycle, reconnect, inventory/economy/reward invariants, matchmaking, idempotency, CCU bursts, hot partitions and fan-out.
