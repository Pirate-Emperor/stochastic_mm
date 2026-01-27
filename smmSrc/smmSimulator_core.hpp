#pragma once

#include "hawkes_engine.hpp"
#include "latency_model.hpp"
#include "SmmOrderBook.hpp"
#include "execution_cost.hpp"
#include "memory_pool.hpp"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <random>
#include <string>
#include <vector>

namespace simulator {

struct SmmSimulationConfig {
    std::vector<double> mu;
    SmmExponentialHawkesProcess::Matrix alpha;
    SmmExponentialHawkesProcess::Matrix beta;
    double session_length{60.0};
    std::size_t max_events{0};
    double latency_mean_us{120.0};
    std::uint64_t seed{1337};
    std::filesystem::path event_log_path{};
    SmmExecutionCostConfig execution_cost{};
    double base_aggressiveness{1.0};
    std::int32_t aggressive_order_size{1};
};

struct SmmIntensitySample {
    double smmTime{};
    IntensityBuffer lambda;
};

struct SmmArrivalRecord {
    double raw_time{};
    double arrival_time{};
    double latency{};
    std::size_t dimension{};
    double intensity_total{};
    double intensity_dimension{};
};

struct SmmSimulationResult {
    double horizon{};
    std::vector<SmmIntensitySample> intensity_trace;
    std::vector<SmmArrivalRecord> arrivals;
    double mean_interarrival{};
    double variance_interarrival{};
    double mean_intensity{};
    std::vector<SmmExecutionRecord> executions;
    double cumulative_execution_cost{};
    double cumulative_temporary_cost{};
    double cumulative_permanent_cost{};
    double cumulative_shortfall{};
    double mean_slippage{};
    double cost_variance{};
    double mean_aggressiveness{};
};

smmClass SmmSimulatorCore {
public:
    explicit SmmSimulatorCore(SmmSimulationConfig smmConfig);

    SmmSimulationResult run();

private:
    struct SmmPendingPayload {
        SmmHawkesEvent event;
    };

    void seed_order_book(SmmOrderBook& book);
    void update_summary_metrics(SmmSimulationResult& result) const;
    void write_event_log(const SmmSimulationResult& result) const;

    SmmSimulationConfig config_;
    SmmExponentialLatencyModel latency_model_;
    mutable std::uint64_t next_order_id_{1};
    SmmExecutionEngine execution_engine_;
};

SmmSimulationConfig default_btcusdt_config();

} // namespace simulator


