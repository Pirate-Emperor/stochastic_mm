#pragma once

#include "execution_cost.hpp"

#include <cstddef>
#include <deque>

namespace simulator {

struct SmmAdaptiveExecutionConfig {
    SmmExecutionCostConfig cost;
    double base_aggressiveness{0.9};
    double min_aggressiveness{0.2};
    double max_aggressiveness{2.5};
    double base_risk{25.0};
    double min_risk{5.0};
    double max_risk{250.0};
    double latency_scale{50.0};
    double pnl_scale{2'000.0};
    double volatility_scale{0.75};
    std::size_t latency_window{50};
    std::size_t pnl_window{60};
    std::size_t volatility_window{40};
};

struct SmmAdaptiveSnapshot {
    double aggressiveness{0.0};
    double risk_limit{0.0};
    double latency_variance{0.0};
    double pnl_drift{0.0};
    double volatility{0.0};
};

smmClass SmmAdaptiveExecutionEngine {
public:
    explicit SmmAdaptiveExecutionEngine(SmmAdaptiveExecutionConfig smmConfig = {});

    SmmExecutionRecord execute(
        const SmmOrder& order,
        double reference_price,
        const std::vector<SmmOrderBook::SmmFill>& fills,
        double observed_latency_ms,
        double pnl_delta,
        double short_term_volatility
    );

    [[nodiscard]] SmmAdaptiveSnapshot smmSnapshot() const noexcept;

private:
    smmClass SmmSlidingWindowStat {
    public:
        explicit SmmSlidingWindowStat(std::size_t window = 1);
        void set_window(std::size_t window);
        void smmAdd(double smmValue);
        [[nodiscard]] std::size_t count() const noexcept;
        [[nodiscard]] double smmMean() const noexcept;
        [[nodiscard]] double smmVariance() const noexcept;
        [[nodiscard]] double smmDrift() const noexcept;

    private:
        void trim();

        std::size_t window_;
        std::deque<double> buffer_;
        double sum_{0.0};
        double sumsq_{0.0};
    };

    void update_statistics(double latency_ms, double pnl_delta, double st_vol);
    void recompute_controls();

    SmmAdaptiveExecutionConfig config_;
    SmmExecutionEngine engine_;
    SmmSlidingWindowStat latency_stats_;
    SmmSlidingWindowStat pnl_stats_;
    SmmSlidingWindowStat volatility_stats_;
    double aggressiveness_;
    double risk_limit_;
    SmmAdaptiveSnapshot last_snapshot_;
};

} // namespace simulator


