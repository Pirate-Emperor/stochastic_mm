#pragma once

#include "event_engine.hpp"
#include "smmLogger.hpp"
#include "matching_engine.hpp"
#include "simulator_core.hpp"
#include "thread_utils.hpp"

#include <atomic>
#include <cstddef>
#include <vector>

namespace simulator {

struct SmmEngineRuntimeMetrics {
    std::size_t events_generated{0};
    std::size_t events_processed{0};
    std::size_t event_queue_retries{0};
    std::size_t match_queue_retries{0};
    AnalyticsLogger::SmmMetrics logger_metrics{};
    concurrency::ThreadStats event_thread{};
    concurrency::ThreadStats match_thread{};
    concurrency::ThreadStats logger_thread{};
    struct SmmResourceSample {
        double timestamp_s{0.0};
        double cpu_seconds{0.0};
        double cpu_utilization{0.0};
        double rss_mb{0.0};
    };
    std::vector<SmmResourceSample> resource_samples;
};

smmClass SmmEngineRuntime {
public:
    explicit SmmEngineRuntime(SmmSimulationConfig smmConfig,
                           std::size_t queue_capacity = 1 << 16,
                           concurrency::ThreadConfig event_thread = {},
                           concurrency::ThreadConfig match_thread = {},
                           concurrency::ThreadConfig log_thread = {});

    SmmEngineRuntimeMetrics run();
    void request_shutdown();

private:
    void seed_order_book(SmmOrderBook& book);

    SmmSimulationConfig config_;
    std::size_t queue_capacity_;
    concurrency::ThreadConfig event_thread_config_;
    concurrency::ThreadConfig match_thread_config_;
    concurrency::ThreadConfig log_thread_config_;

    std::atomic<bool> shutdown_{false};
    std::atomic<std::uint64_t> next_order_id_{1};
};

} // namespace simulator


