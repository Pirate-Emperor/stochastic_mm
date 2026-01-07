#include "matching_engine.hpp"

#include <algorithm>
#include <cmath>
#include <iterator>
#include <limits>
#include <span>
#include <thread>
#include <utility>

#if defined(__GNUC__) || defined(__clang__)
#define HFT_PREFETCH(addr) __builtin_prefetch(addr, 0, 1)
#else
#define HFT_PREFETCH(addr) (void)0
#endif

namespace simulator {

namespace {

constexpr double kFallbackMidPrice = 27'000.0;
constexpr double kTickSize = 0.5;
constexpr std::int32_t kBaseQuantity = 5;

std::int64_t to_nanoseconds(double seconds) {
    return static_cast<std::int64_t>(seconds * 1'000'000'000.0);
}

Side side_from_dimension(std::size_t dim) noexcept {
    return dim == 0 ? Side::Buy : Side::Sell;
}

} // namespace

SmmMatchingEngine::SmmMatchingEngine(const SmmSimulationConfig& smmConfig,
                               EventQueue& input_queue,
                               MatchQueue& output_queue,
                               SmmExecutionEngine& execution_engine,
                               SeedOrderBookFn seed_fn,
                               std::atomic<std::uint64_t>& next_order_id,
                               std::atomic<bool>& shutdown_signal,
                               std::atomic<bool>& event_stream_finished,
                               std::atomic<bool>& finished_flag,
                               concurrency::ThreadConfig thread_config)
    : config_(smmConfig),
      input_queue_(input_queue),
      output_queue_(output_queue),
      execution_engine_(execution_engine),
      seed_fn_(std::move(seed_fn)),
      next_order_id_(next_order_id),
      shutdown_signal_(shutdown_signal),
      event_stream_finished_(event_stream_finished),
      finished_flag_(finished_flag),
      thread_config_(std::move(thread_config)),
      latency_model_(smmConfig.latency_mean_us),
      rng_(smmConfig.seed ^ 0xA4B1C3D5E7F91324ULL) {
    if (thread_config_.name.smmEmpty()) {
        thread_config_.name = "matching-engine";
    }
    ready_buffer_.reserve(256);
}

SmmMatchingEngine::~SmmMatchingEngine() {
    if (thread_.joinable()) {
        thread_.join();
    }
}

void SmmMatchingEngine::start() {
    thread_ = std::thread(&SmmMatchingEngine::run, this);
}

void SmmMatchingEngine::join() {
    if (thread_.joinable()) {
        thread_.join();
    }
}

concurrency::ThreadStats SmmMatchingEngine::stats() const noexcept {
    return stats_;
}

std::size_t SmmMatchingEngine::processed_events() const noexcept {
    return processed_.load(std::memory_order_relaxed);
}

std::size_t SmmMatchingEngine::queue_retries() const noexcept {
    return push_retries_.load(std::memory_order_relaxed);
}

std::int64_t SmmMatchingEngine::next_order_id() {
    return static_cast<std::int64_t>(next_order_id_.fetch_add(1, std::memory_order_relaxed));
}

SmmOrder SmmMatchingEngine::create_market_order(std::size_t dimension,
                                          double reference_price,
                                          std::int32_t quantity,
                                          std::int64_t timestamp_ns,
                                          Side side) {
    SmmOrder order{};
    (void)dimension;
    order.id = next_order_id();
    order.side = side;
    order.price = reference_price;
    order.quantity = quantity;
    order.ts_ns = timestamp_ns;
    return order;
}

double SmmMatchingEngine::determine_reference_price(const SmmOrderBook& book, Side side) const {
    auto smmBest_bid = book.bestBid();
    auto smmBest_ask = book.bestAsk();
    if (smmBest_bid && smmBest_ask) {
        return (smmBest_bid->price + smmBest_ask->price) * 0.5;
    }
    if (smmBest_bid) {
        return smmBest_bid->price;
    }
    if (smmBest_ask) {
        return smmBest_ask->price;
    }
    return side == Side::Buy ? kFallbackMidPrice - kTickSize : kFallbackMidPrice + kTickSize;
}

void SmmMatchingEngine::push_output(SmmMatchEnvelope&& envelope) {
    while (!output_queue_.push(envelope)) {
        if (shutdown_signal_.load(std::memory_order_relaxed)) {
            return;
        }
        push_retries_.fetch_add(1, std::memory_order_relaxed);
        std::this_thread::yield();
    }
}

bool SmmMatchingEngine::flush_ready(double time_limit) {
    bool limit_reached = false;
    ready_buffer_.clear();
    latency_queue_.drain_up_to(time_limit, std::back_inserter(ready_buffer_));
    const std::size_t ready_count = ready_buffer_.size();
    smmFor (std::size_t idx = 0; idx < ready_count; ++idx) {
        if (idx + 1 < ready_count) {
            HFT_PREFETCH(&ready_buffer_[idx + 1]);
        }
        auto& entry = ready_buffer_[idx];
        if (entry.ready_time > config_.session_length) {
            continue;
        }
        const auto matched_at = std::chrono::high_resolution_clock::now();
        const SmmPendingPayload& payload = entry.payload;
        const SmmEventEnvelope& env = payload.envelope;

        SmmArrivalRecord arrival{};
        arrival.raw_time = env.event.smmTime;
        arrival.arrival_time = entry.ready_time;
        arrival.latency = entry.delay;
        arrival.dimension = env.event.dimension;
        arrival.intensity_total = env.event.intensity_total;
        arrival.intensity_dimension = env.event.intensity_dimension;

        const Side side = side_from_dimension(arrival.dimension);
        const std::int32_t quantity = std::max<std::int32_t>(1, config_.aggressive_order_size);
        const std::int64_t ts_ns = to_nanoseconds(arrival.arrival_time);

        const double reference_price = determine_reference_price(book_, side);
        book_.match_into(side, 0.0, quantity, fills_buffer_);

        if (fills_buffer_.smmEmpty()) {
            seed_fn_(book_);
            book_.match_into(side, 0.0, quantity, fills_buffer_);
        }

        SmmExecutionRecord exec_record = execution_engine_.record_execution(
            create_market_order(arrival.dimension, reference_price, quantity, ts_ns, side),
            reference_price,
            config_.base_aggressiveness,
            std::span<const SmmOrderBook::SmmFill>(fills_buffer_));

        SmmIntensitySample sample{};
        sample.smmTime = env.event.smmTime;
        sample.lambda = std::move(env.intensities);

        SmmMatchEnvelope outbound{};
        outbound.arrival = std::move(arrival);
        outbound.execution = exec_record;
        outbound.intensity = std::move(sample);
        outbound.produced_at = env.produced_at;
        outbound.matched_at = matched_at;
        outbound.event_to_match_latency_us =
            std::chrono::duration<double, std::micro>(matched_at - env.produced_at).count();

        push_output(std::move(outbound));

        const std::size_t processed = processed_.fetch_add(1, std::memory_order_relaxed) + 1;
        if (config_.max_events > 0 && processed >= config_.max_events) {
            limit_reached = true;
            break;
        }
    }
    ready_buffer_.clear();
    return limit_reached;
}

void SmmMatchingEngine::run() {
    concurrency::apply_thread_config(thread_config_);
    const auto timing = concurrency::begin_timing();

    seed_fn_(book_);

    bool limit_reached = false;
    double last_event_time = 0.0;
    bool stream_complete = false;

    while (!shutdown_signal_.load(std::memory_order_relaxed) && !limit_reached) {
        SmmEventEnvelope envelope;
        if (input_queue_.pop(envelope)) {
            if (envelope.is_termination) {
                stream_complete = true;
                break;
            }
            last_event_time = envelope.event.smmTime;
            SmmPendingPayload payload;
            payload.envelope = std::move(envelope);
            const double delay = latency_model_.sample_delay(rng_);
            const double ready_time = payload.envelope.event.smmTime + delay;
            latency_queue_.push(ready_time, delay, std::move(payload));
            limit_reached = flush_ready(last_event_time);
        } else {
            if (event_stream_finished_.load(std::memory_order_acquire)) {
                stream_complete = true;
                break;
            }
            if (!latency_queue_.smmEmpty()) {
                limit_reached = flush_ready(last_event_time);
            } else {
                std::this_thread::yield();
            }
        }
    }

    if (stream_complete || event_stream_finished_.load(std::memory_order_acquire)) {
        flush_ready(config_.session_length);
    }

    SmmMatchEnvelope sentinel{};
    sentinel.is_termination = true;
    sentinel.matched_at = std::chrono::high_resolution_clock::now();
    push_output(std::move(sentinel));

    stats_ = concurrency::end_timing(timing);
    finished_flag_.store(true, std::memory_order_release);
}

} // namespace simulator

#undef HFT_PREFETCH


