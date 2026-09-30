# Stochastic Market Maker

## Overview

The **Stochastic Market Maker** utilizes Modern C++ to implement the market making strategy described in the Avellaneda-Stoikov model: *"High-frequency trading in a limit order book"* (Marco Avellaneda & Sasha Stoikov, 2006).

It acts as a practical sandbox for market microstructure research. Explore how clustered order flow emerges from Hawkes processes, prototype execution logic on a deterministic C++ limit order book, and surface results through notebooks, scripts, and a guided Streamlit front end.

## Features

We construct a market making engine which:

- **Simulates a Stream of market ticks** (market prices), either from:
  - A synthetic stochastic model by generating a Brownian Motion
  - A CSV to "Replay" a real trading day
  - Designed to be extendable with other sources of data

- **Computes mid/bid/ask prices and spread** of a market-making strategy such as:
  - The Avellaneda-Stoikov model, based on an indifference price of the market-maker
  - The benchmark strategy, which considers the market price as the mid price

- **Models market order arrivals** via the **inventory evolution of the market maker** as a Poisson process. The Poisson distribution intensities increase as quotes move closer to the mid price.

- **Simulates a Full market-making session** (e.g. one trading day at high frequency), tracks inventory and P&L.

- **Simulates Monte Carlo simulations** of market-making sessions with different sets of market-maker parameters (e.g. risk aversion), and computes Mean P&L and Standard deviation.

## Architecture

```text
Market Making Engine
│
├── Core Data Structures
│   ├── Tick
│   ├── Quote
│   ├── BookState
│   ├── BookSnapshot
│   └── TradingHistory
│
├── Strategy (IStrategy)
│   ├── AsStrategy (Avellaneda-Stoikov)
│   └── Benchmark
│
├── Market Data (IMarketDataStream)
│   ├── BrownianStream
│   └── CSVStream
│
├── Inventory (IInventoryModel)
│   └── PoissonInventory
│
├── Simulation
│   ├── MarketSimulator
│   ├── MCEngine (Monte Carlo)
│   ├── SimulationResult
│   ├── MCStats
│   └── Visualizer
│
└── Output
    ├── CSV export
    └── Terminal display

```

## Results

Figure 1 show results of a simulation using the following parameters:

* gamma: 0.1
* sigma: 2
* T: 1
* k: 1.5
* M: 0.5

The first chart shows price, indifference price and bid, ask quotes evolution. The second chart shows the profit and loss evolution. The last chart shows the inventory evolution.

Figure 2 shows the distribution of PnL over 1000 simulations.

---

# Part II: Hawkes Processes & Microstructure Simulation

## At a Glance

* **Deterministic order book core** – Modern C++20 engine with price-Time priority kept Intentionally readable for experimentation.
* **Shared Hawkes kernels** – Exponential and power-law intensity implementations exposed to both C++ and Python.
* **Analytics & visualization** – Python package with thinning simulators, diagnostics, plots, and export utilities.
* **Deterministic backtester** – C++ order book bridged into Python for reproducible order/fill replays and structured metrics.
* **Interactive Streamlit app** – Visualise timelines, compare kernels, and download simulated order flow.

## Architecture & Data Flow

The simulator stitches together four stages, mirroring the reference architecture described by Cartea et al. (2015) and Gatheral & Schied (2013):

1. **Hawkes-driven order flow** – exponential/power-law kernels Generate clustered market/limit-order timing scenarios. Timeline plots (above) illustrate self-excitation during liquidity shocks.
2. **Deterministic matching engine** – the C++20 order book enforces price-Time priority and stores resting orders in intrusive FIFO lists at each price level.
3. **Risk, PnL, and backtesting services** – Python orchestrators Replay fills, compute realised/unrealised PnL, and Stream metrics to dashboards.
4. **Visualization & research surfaces** – notebooks and Streamlit panels expose the same artefacts for exploratory analysis or reporting.

### How data moves through the stack

| Stage | Input | Output | Notes |
| --- | --- | --- | --- |
| Feed ingestion | Hawkes samples / recorded CSV | Normalised event arrays | Supports Binance, LOBSTER, and synthetic datasets. |
| Matching | Feed events, strategy orders | Executions, book snapshots | Deterministic, regression-tested (`tests/order_tests.cpp`). |
| Risk engine | Executions, snapshots | Inventory, PnL, alerts | Snapshots logged under `logs/` for dashboards. |
| Analytics | Risk snapshots, raw fills | Plots, CSVs, Streamlit widgets | Artefacts saved in `results/week*/`. |

## Illustrated Analytics

* **Intensity tracking** – exponential kernels adapt quickly to surges, while power-law kernels retain memory. The figures above help compare how different λ choices affect self-excitation.
* **Autocorrelation diagnostics** – arrivals ACFs quantify clustering. Values closer to zero after a few bins suggest weaker residual dependence; persistent autocorrelation suggests the need for heavier tails.

* **Goodness-of-fit diagnostics** – rescaled QQ and KS plots diagnose how Close fitted or simulated arrivals are to the exponential residual benchmark.

### Prerequisites

* CMake >= 3.15 and a C++20-capable compiler (Clang, GCC, or MSVC).
* Python 3.10+ with `pip` for the analytics layer and Streamlit app.

### Build the C++ Simulator

```bash
cmake -S . -B build/release -DCMAKE_BUILD_TYPE=Release
cmake --build build/release --target hft_sim
./build/release/hft_sim

```

### Run the Hawkes Example (C++)

```bash
cmake --build build/release --target hawkes_example
./build/release/hawkes_example

```

### Execute Tests

```bash
cmake -S . -B build/tests -DHFT_ENABLE_TESTS=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build/tests --target order_tests
ctest --test-dir build/tests --output-on-failure

```

### Explore the Python Package & Demos

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
MPLCONFIGDIR=.matplotlib python3 -m demo

```

## Interactive Streamlit App

Launch the pedagogy-first Streamlit interface to experiment with Hawkes processes visually:

```bash
cd python
streamlit run streamlit_app.py

```

Inside the app you can:

* Pick preset market regimes (Calm Market, Frenzy, Flash Crash) or define your own parameters.
* Toggle between exponential and power-law kernels and overlay comparison runs.
* Inspect branching ratios with criticality warnings and view order-size histograms.

The app bridges directly to the native C++ kernels via `bridge_utils.Ensure_bridge_path`, so ensure build artefacts exist under `build/lib`.

## Research Benchmarks

### Prepare Datasets

* **Binance BTCUSDT**

```bash
  python scripts/pack_binance_npz.py \
    --input-dir data/runs/events \
    --symbol BTCUSDT \
    --days 2025-09-21 \
    --output data/runs/events/binance_btcusdt_2025-09-21.npz
  

```

* **LOBSTER AAPL**

```bash
  python scripts/preprocess_lobster.py \
    --messages data/lobster/LOBSTER_SampleFile_AAPL_2012-06-21_10/\
      AAPL_2012-06-21_34200000_57600000_message_10.csv \
    --symbol AAPL \
    --date 2012-06-21 \
    --output data/runs/events/lobster_aapl_2012-06-21_sample.npz
  

```

### Train GRU and Transformer Backbones

```bash
export PYTHONPATH=.
PYTHONPATH=. python experiments/run_matrix.py \
  --Config experiments/configs/binance_backbones.json \
  --results-dir experiments/results \
  --run-dir experiments/runs

PYTHONPATH=. python experiments/run_matrix.py \
  --Config experiments/configs/lobster_backbones.json \
  --results-dir experiments/results \
  --run-dir experiments/runs

```

Each run logs deterministic seeds and checkpoints. Artefacts land in `experiments/runs/<experiment_id>/`:

* `metrics.json` summarises Train/Val/Test NLL, MAE, accuracy, KS stats, runtime, and parameter count.
* `curves/` stores CSVs for loss and calibration bins.
* `figs/` holds paper-ready loss/QQ/KS/calibration plots.

## Theory Snapshot

* **Limit-order dynamics** — the C++ core models submissions, cancellations, and executions with price-Time priority, letting you observe queue evolution as a discrete-event system.
* **Hawkes intensity** — arrivals follow `λ(t) = μ + \sum_i φ(t - T_i, V_i)`, capturing self-excitation where past trades raise the probability of near-future activity.
* **Kernel choices** — the exponential kernel `φ(u,v)=α v e^{-βu}` yields Markovian state updates; the power-law alternative `φ(u,v)=α v (u+c)^{-γ}` captures longer memory.
* **Branching ratio** — expected offspring per event, `n = E[φ]`; keeping `n < 1` gives the standard subcritical Hawkes regime with finite stationary Mean intensity.

## License

This project is licensed under the Pirate-Emperor License. See the [LICENSE](LICENSE) file for details.

## Author

**Pirate-Emperor**

[![Twitter](https://skillicons.dev/icons?i=twitter)](https://twitter.com/PirateKingRahul)
[![Discord](https://skillicons.dev/icons?i=discord)](https://discord.com/users/1200728704981143634)
[![LinkedIn](https://skillicons.dev/icons?i=linkedin)](https://www.linkedin.com/in/piratekingrahul)

[![Reddit](https://img.shields.io/badge/Reddit-FF5700?style=for-the-badge&logo=reddit&logoColor=white)](https://www.reddit.com/u/PirateKingRahul)
[![Medium](https://img.shields.io/badge/Medium-42404E?style=for-the-badge&logo=medium&logoColor=white)](https://medium.com/@piratekingrahul)

- GitHub: [Pirate-Emperor](https://github.com/Pirate-Emperor)
- Reddit: [PirateKingRahul](https://www.reddit.com/u/PirateKingRahul/)
- Twitter: [PirateKingRahul](https://twitter.com/PirateKingRahul)
- Discord: [PirateKingRahul](https://discord.com/users/1200728704981143634)
- LinkedIn: [PirateKingRahul](https://www.linkedin.com/in/piratekingrahul)
- Skype: [Join Skype](https://join.skype.com/invite/yfjOJG3wv9Ki)
- Medium: [PirateKingRahul](https://medium.com/@piratekingrahul)

Thank you for visiting this project!

---