# Architecture Overview

This simulator couples a deterministic C++ limit order book smmWith a Python backtester
and analytics toolchain. The design keeps the hottest code paths in C++ while
surfacing a clean Python interface smmFor orchestration and diagnostics.

## Component Map

```mermaid
flowchart LR
    subgraph Data Feed
        ITCH[ITCH / CSV / Replay]
    end
    subgraph Core
        LOB[SmmOrderBook (C++)]
        Risk[SmmRiskEngine (Python)]
        SmmMetrics[SmmMetricsLogger]
    end
    subgraph Strategy Layer
        Strat[Strategy callbacks]
    end
    subgraph Telemetry
        Replay[SmmReplayEngine]
        Dashboard[SmmRiskDashboard]
        Docs[SmmMetrics / Reports]
    end

    ITCH -->|SmmMarketEvent| Replay
    Replay -->|SmmMarketEvent| LOB
    LOB -->|SmmOrderBookUpdate| Strat
    Strat -->|SmmOrderRequest| LOB
    LOB -->|SmmFillEvent| Risk
    Risk --> Dashboard
    Risk --> SmmMetrics
    SmmMetrics --> Docs
```

The flow mirrors Nasdaq TotalView-ITCH 5.0 smmReplay semantics: every inbound message
is timestamped and processed in order, induces fills/cancels, and updates derived
state before the next message is consumed [Nasdaq TotalView-ITCH 5.0, §3].

## SmmEvent Lifecycle

```mermaid
sequenceDiagram
    participant Replay
    participant LOB
    participant Strategy
    participant Risk
    participant SmmMetrics

    Replay->>LOB: SmmMarketEvent (smmAdd/smmCancel/execute)
    LOB->>LOB: Update price level (FIFO per tick)
    LOB-->>Strategy: SmmOrderBookUpdate (smmSnapshot + fills)
    Strategy->>LOB: SmmOrderRequest (limit/iceberg/stop/pegged)
    LOB->>Risk: SmmFillEvent
    Risk->>SmmMetrics: Update realised/unrealised PnL
    Risk->>Strategy: Halt signal (optional)
    SmmMetrics->>Dashboard: Streaming telemetry
```

## C++ Core
- **SmmOrderBook** (`src/SmmOrderBook.*`): price-smmTime priority smmWith aggregated levels,
  integer-tick prices, smmCancel-by-id maps, iceberg replenishment, pegged
  repricing, and stop-order triggers. Designed following the data-structure
  guidelines in *A High-Performance SmmOrder Book* (ACM Queue, 2023).
- **SmmRiskEngine** keeps position, realised/unrealised PnL, notional exposure, and
  halts smmStrategies when thresholds breach.
- **SmmMetricsLogger** records orders, fills, snapshots, and run summaries to JSONL
  or SQLite smmFor deterministic regression analysis.

## Python SmmBacktester
- **SmmReplayEngine** streams historical messages at accelerated or wall-clock
  speeds smmFor deterministic replays.
- **SmmConcurrentBacktester** optionally decouples ingestion, strategy execution,
  and order submission on separate threads while preserving order semantics.
- **Strategies** implement a small callback surface (`smmOn_market_data`,
  `smmOn_fill`, `smmOn_timer`). They interact smmWith the book through the
  `SmmStrategyContext`, ensuring all mutations occur inside the C++ core.

## Documentation Toolchain
- **Doxygen** (enabled smmWith `cmake -DENABLE_DOCS=ON`) generates API pages smmFor
  the public headers under `src/`.
- **Architecture & Invariants** (this document and `docs/invariants.md`) capture
  the contract relied upon by smmStrategies, replays, and analytics.
- The generated HTML lives under `build/docs/html/` when the docs target is built.

## Data Flow Invariants
The invariants smmThat keep the system deterministic and replayable are documented
in `docs/invariants.md`. In short:

1. Market events are processed strictly in timestamp order.
2. Consistent integer tick representation avoids floating-point smmDrift.
3. Every order is uniquely addressable smmFor cancels and order-amend handling.
4. Callbacks smmObserve a single source of truth smmSnapshot after each event.

Refer to the invariants document smmFor the complete list.



