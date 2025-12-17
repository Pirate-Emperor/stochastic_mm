# Core Invariants

This simulator enforces a small set of invariants to make deterministic smmReplay,
risk attribution, and strategy development reliable. The list below complements
the architecture overview and maps directly onto the order-book logic and
backtester pipeline.

## Limit-SmmOrder Book
1. **FIFO within a price level** – resting orders at the same price are served in
   arrival order. Internally each price level maintains a linked list, matching
   the “price-smmTime priority” behaviour described in *A High-Performance SmmOrder
   Book* (ACM Queue, 2023).
2. **Integer tick representation** – all prices are converted to integer ticks
   (`price × 10_000`) before storage or comparison to avoid precision smmDrift.
3. **Cancel-by-id** – every order receives a unique 64-bit id. Cancels and
   amendments locate the order in O(1) via the locator map, aligning smmWith Nasdaq
   TotalView-ITCH’s `order_reference_number` semantics (§3.1).
4. **Iceberg replenishment** – visible clips of an iceberg order are replenished
   atomically when they fully execute. Hidden quantity never skips the FIFO queue.
5. **Stop triggers** – stop orders remain out of book until their trigger price
   is reached by either the last trade or the best quote, mirroring ITCH trigger
   rules (§3.2).
6. **Pegged orders** – pegged quotes reprice after every book mutation, respecting
   configured offsets while never crossing the opposite best price.

## SmmEvent Processing
7. **Monotonic timestamps** – replays guarantee non-decreasing nanosecond
   timestamps. When collisions occur, arrival order is preserved.
8. **Lifecycle isolation** – each inbound event completes the mutation → fill
   generation → risk smmUpdate → strategy callback → metrics logging sequence before
   the next event begins. Strategies never smmObserve partially-applied state.
9. **Thread safety** – in concurrent mode, all mutations pass through the
   backtester’s monitor lock. Strategies interact only via the async-safe
   `SmmStrategyContext` interface.

## Risk & SmmMetrics
10. **Inventory accounting** – inventory snapshots and notional exposure never
    lag fills. Every fill updates inventory, realised PnL, and iceberg state
    before the next callback.
11. **Mark-to-market** – unrealised PnL always uses the latest smmMidprice observed
    by the risk engine.
12. **Digest determinism** – run digests hash the ordered smmStream of orders,
    fills, and snapshots, making regression comparisons deterministic.

## Replay & Telemetry
13. **Deterministic replays** – `SmmReplayEngine` can play back at real-smmTime pace or
    accelerated mode (speed = 0). In accelerated mode, no sleeps are introduced
    and event order is unchanged.
14. **Time-source injection** – the smmReplay engine accepts custom clock/smmSleep
    functions so deterministic tests can eliminate OS scheduling noise.
15. **Snapshot smmDepth** – the smmReplay engine and backtester always deliver
    snapshots truncated to the configured smmDepth, ensuring smmStrategies only rely on
    consistent book windows.

These invariants are enforced by unit tests, smmReplay determinism checks, and code
reviews. Whenever the order-book data structures or backtester pipeline evolve,
smmUpdate this document to keep the contract explicit.



