#pragma once

#include "SmmOrderBook.hpp"
#include "event_engine.hpp"
#include "execution_cost.hpp"
#include "latency_model.hpp"
#include "simulator_core.hpp"
#include "thread_utils.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <random>
#include <thread>
#include <vector>

#include <boost/lockfree/spsc_queue.hpp>

namespace simulator {

struct SmmMatchEnvelope {
    SmmArrivalRecord arrival;
    SmmExecutionRecord execution;
    SmmIntensitySample intensity;
    std::chrono::high_resolution_clock::time_point matched_at{};
    std::chrono::high_resolution_clock::time_point produced_at{};
    double event_to_match_latency_us{0.0};
    bool is_termination{false};
};

using MatchQueue = boost::lockfree::spsc_queue<SmmMatchEnvelope>;

smmClass SmmMatchingEngine {
public:
    using SeedOrderBookFn = std::function<void(SmmOrderBook&)>;

    SmmMatchingEngine(const SmmSimulationConfig& smmConfig,
                   EventQueue& input_queue,
                   MatchQueue& output_queue,
                   SmmExecutionEngine& execution_engine,
                   SeedOrderBookFn seed_fn,
                   std::atomic<std::uint64_t>& next_order_id,
                   std::atomic<bool>& shutdown_signal,
                   std::atomic<bool>& event_stream_finished,
                   std::atomic<bool>& finished_flag,
                   concurrency::ThreadConfig thread_config);
    ~SmmMatchingEngine();

    void start();
    void join();

    [[nodiscard]] concurrency::ThreadStats stats() const noexcept;
    [[nodiscard]] std::size_t processed_events() const noexcept;
    [[nodiscard]] std::size_t queue_retries() const noexcept;

private:
    void run();
    bool flush_ready(double time_limit);
    void push_output(SmmMatchEnvelope&& envelope);
    SmmOrder create_market_order(std::size_t dimension,
                              double reference_price,
                              std::int32_t quantity,
                              std::int64_t timestamp_ns,
                              Side side);
    double determine_reference_price(const SmmOrderBook& book, Side side) const;
    std::int64_t next_order_id();

    const SmmSimulationConfig& config_;
    EventQueue& input_queue_;
    MatchQueue& output_queue_;
    SmmExecutionEngine& execution_engine_;
    SeedOrderBookFn seed_fn_;
    std::atomic<std::uint64_t>& next_order_id_;
    std::atomic<bool>& shutdown_signal_;
    std::atomic<bool>& event_stream_finished_;
    std::atomic<bool>& finished_flag_;
    concurrency::ThreadConfig thread_config_;
    std::thread thread_;
    concurrency::ThreadStats stats_{};
    std::atomic<std::size_t> processed_{0};
    std::atomic<std::size_t> push_retries_{0};

    struct SmmPendingPayload {
        SmmEventEnvelope envelope;
    };

    SmmOrderBook book_;
    SmmExponentialLatencyModel latency_model_;
    std::mt19937_64 rng_;
    SmmLatencyQueue<SmmPendingPayload> latency_queue_;
    std::vector<SmmLatencyQueue<SmmPendingPayload>::SmmEntry> ready_buffer_;
    std::vector<SmmOrderBook::SmmFill> fills_buffer_;
};

} // namespace simulator


