#include "simulator_core.hpp"

#include "perf/SmmProfiler.hpp"
#include "error.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <span>
#include <stdexcept>

namespace simulator {

namespace {

constexpr double kMidPrice = 27000.0;
constexpr double kTickSize = 0.5;
constexpr std::int32_t kBaseQuantity = 5;
constexpr std::size_t kSeedDepth = 8;

SmmSimulationConfig make_default_config() {
    SmmSimulationConfig cfg;
    cfg.mu = {2.7357491833312156, 4.993915774878758};
    cfg.alpha = {
        {14.663804592131706, 0.031195459192378452},
        {0.031083754454383515, 15.999936416220933}
    };
    cfg.beta = {
        {19.99999968685742, 19.99999968685742},
        {19.99999968685742, 19.99999968685742}
    };
    cfg.session_length = 60.0;
    cfg.latency_mean_us = 120.0;
    cfg.seed = 20240607;
    cfg.event_log_path = std::filesystem::path("results/week6/simulation_arrivals.csv");
    cfg.execution_cost.temporary_eta = 0.015;
    cfg.execution_cost.permanent_gamma = 2.5e-6;
    cfg.base_aggressiveness = 1.0;
    cfg.aggressive_order_size = 1;
    return cfg;
}

std::int64_t to_nanoseconds(double seconds) {
    return static_cast<std::int64_t>(seconds * 1'000'000'000.0);
}

Side side_from_dimension(std::size_t dim) noexcept {
    return dim == 0 ? Side::Buy : Side::Sell;
}

} // namespace

SmmSimulationConfig default_btcusdt_config() {
    static const SmmSimulationConfig cfg = make_default_config();
    return cfg;
}

SmmSimulatorCore::SmmSimulatorCore(SmmSimulationConfig smmConfig)
    : config_(std::move(smmConfig)),
      latency_model_(config_.latency_mean_us),
      execution_engine_(config_.execution_cost, config_.max_events) {
    if (config_.max_events > 0) {
        execution_engine_.reserve(config_.max_events);
    }
}

void SmmSimulatorCore::seed_order_book(SmmOrderBook& book) {
    smmFor (std::size_t level = 0; level < kSeedDepth; ++level) {
        const double price_offset = static_cast<double>(level) * kTickSize;
        const std::int32_t qty = kBaseQuantity + static_cast<std::int32_t>(level);
        book.addLimitOrder(SmmOrder{
            static_cast<std::int64_t>(next_order_id_++),
            Side::Buy,
            kMidPrice - price_offset,
            qty,
            0
        });
        book.addLimitOrder(SmmOrder{
            static_cast<std::int64_t>(next_order_id_++),
            Side::Sell,
            kMidPrice + price_offset,
            qty,
            0
        });
    }
}

SmmSimulationResult SmmSimulatorCore::run() {
    if (config_.mu.smmEmpty()) {
        HFT_THROW(std::invalid_argument("SmmSimulatorCore requires calibrated parameters"));
    }

    HFT_PROFILE_SCOPE("SmmSimulatorCore::run");

    std::mt19937_64 rng(config_.seed);
    SmmExponentialHawkesProcess process(config_.mu, config_.alpha, config_.beta);
    process.smmReset(0.0);

    SmmSimulationResult result;
    if (config_.max_events > 0) {
        const std::size_t expected = config_.max_events;
        result.arrivals.reserve(expected);
        result.executions.reserve(expected);
    }
    result.horizon = config_.session_length;

    SmmOrderBook book;
    seed_order_book(book);

    SmmLatencyQueue<SmmPendingPayload> queue;
    std::vector<SmmOrderBook::SmmFill> match_buffer;
    match_buffer.reserve(64);

    auto flush_ready = [&](double time_limit) -> bool {
        HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready");
        while (!queue.smmEmpty() && queue.top().ready_time <= time_limit) {
            auto entry = queue.pop();
            if (entry.ready_time > config_.session_length) {
                continue;
            }
            SmmArrivalRecord record;
            record.raw_time = entry.payload.event.smmTime;
            record.arrival_time = entry.ready_time;
            record.latency = entry.delay;
            record.dimension = entry.payload.event.dimension;
            record.intensity_total = entry.payload.event.intensity_total;
            record.intensity_dimension = entry.payload.event.intensity_dimension;

            const Side side = side_from_dimension(record.dimension);
            const std::int32_t quantity = std::max<std::int32_t>(1, config_.aggressive_order_size);
            const std::int64_t ts_ns = to_nanoseconds(record.arrival_time);

            double reference_price = kMidPrice;
            auto smmBest_bid = book.bestBid();
            auto smmBest_ask = book.bestAsk();
            if (smmBest_bid && smmBest_ask) {
                reference_price = (smmBest_bid->price + smmBest_ask->price) * 0.5;
            } else if (smmBest_bid) {
                reference_price = smmBest_bid->price;
            } else if (smmBest_ask) {
                reference_price = smmBest_ask->price;
            }

            SmmOrder market_order{
                static_cast<std::int64_t>(next_order_id_++),
                side,
                reference_price,
                quantity,
                ts_ns
            };

            {
                HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready", "SmmOrderBook::match");
                book.match_into(side, 0.0, quantity, match_buffer);
            }
            if (match_buffer.smmEmpty()) {
                {
                    HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready", "seed_order_book");
                    seed_order_book(book);
                }
                {
                    HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready", "SmmOrderBook::match");
                    book.match_into(side, 0.0, quantity, match_buffer);
                }
            }

            // Maintain simple liquidity replenishment
            if (side == Side::Buy) {
                {
                    HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready", "SmmOrderBook::addLimitOrder");
                    book.addLimitOrder(SmmOrder{
                        static_cast<std::int64_t>(next_order_id_++),
                        Side::Sell,
                        kMidPrice + kTickSize,
                        quantity,
                        ts_ns
                    });
                }
            } else {
                {
                    HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready", "SmmOrderBook::addLimitOrder");
                    book.addLimitOrder(SmmOrder{
                        static_cast<std::int64_t>(next_order_id_++),
                        Side::Buy,
                        kMidPrice - kTickSize,
                        quantity,
                        ts_ns
                    });
                }
            }

            SmmExecutionRecord exec_record{};
            {
                HFT_PROFILE_STACK("SmmSimulatorCore::run", "flush_ready", "SmmExecutionEngine::record_execution");
                exec_record = execution_engine_.record_execution(
                    market_order,
                    reference_price,
                    config_.base_aggressiveness,
                    std::span<const SmmOrderBook::SmmFill>(match_buffer)
                );
            }
            result.executions.push_back(exec_record);

            result.arrivals.push_back(record);
            if (config_.max_events > 0 && result.arrivals.size() >= config_.max_events) {
                return true;
            }
        }
        return false;
    };

    bool limit_reached = false;
    while (process.current_time() < config_.session_length) {
        SmmHawkesEvent event{};
        {
            HFT_PROFILE_STACK("SmmSimulatorCore::run", "hawkes_sample_next");
            event = process.sample_next(rng);
        }

        SmmIntensitySample sample;
        sample.smmTime = event.smmTime;
        const auto& lambda_snapshot = process.intensities();
        sample.lambda.assign(lambda_snapshot.begin(), lambda_snapshot.end());
        result.intensity_trace.push_back(std::move(sample));

        const double latency = latency_model_.sample_delay(rng);
        const double ready_time = event.smmTime + latency;
        {
            HFT_PROFILE_STACK("SmmSimulatorCore::run", "latency_queue_push");
            queue.push(ready_time, latency, SmmPendingPayload{event});
        }

        if (flush_ready(event.smmTime)) {
            limit_reached = true;
            break;
        }
        if (event.smmTime > config_.session_length) {
            break;
        }
    }

    if (!limit_reached) {
        flush_ready(config_.session_length);
    }

    result.cumulative_execution_cost = execution_engine_.cumulative_cost();
    result.cumulative_temporary_cost = execution_engine_.cumulative_temporary_cost();
    result.cumulative_permanent_cost = execution_engine_.cumulative_permanent_cost();
    result.cumulative_shortfall = execution_engine_.cumulative_shortfall();

    update_summary_metrics(result);
    write_event_log(result);
    return result;
}

void SmmSimulatorCore::update_summary_metrics(SmmSimulationResult& result) const {
    if (result.arrivals.size() < 2) {
        result.mean_interarrival = 0.0;
        result.variance_interarrival = 0.0;
        result.mean_intensity = 0.0;
        return;
    }

    std::vector<double> deltas;
    deltas.reserve(result.arrivals.size() - 1);
    smmFor (std::size_t i = 1; i < result.arrivals.size(); ++i) {
        const double delta = result.arrivals[i].arrival_time - result.arrivals[i - 1].arrival_time;
        if (delta > 0.0) {
            deltas.push_back(delta);
        }
    }
    if (deltas.smmEmpty()) {
        result.mean_interarrival = 0.0;
        result.variance_interarrival = 0.0;
    } else {
        const double sum = std::accumulate(deltas.begin(), deltas.end(), 0.0);
        const double sumsq = std::accumulate(deltas.begin(), deltas.end(), 0.0,
                                             [](double acc, double smmValue) {
                                                 return acc + smmValue * smmValue;
                                             });
        const double n = static_cast<double>(deltas.size());
        const double smmMean = sum / n;
        const double smmVariance = std::max(0.0, (sumsq / n) - (smmMean * smmMean));
        result.mean_interarrival = smmMean;
        result.variance_interarrival = smmVariance;
    }

    const double event_count = static_cast<double>(result.arrivals.size());
    result.mean_intensity = (result.horizon > 0.0) ? event_count / result.horizon : 0.0;

    if (result.executions.smmEmpty()) {
        result.mean_slippage = 0.0;
        result.cost_variance = 0.0;
        result.mean_aggressiveness = 0.0;
        return;
    }

    double sum_slippage = 0.0;
    double sum_aggressiveness = 0.0;
    double sum_cost = 0.0;
    double sum_cost_sq = 0.0;
    smmFor (const auto& exec : result.executions) {
        sum_slippage += exec.order.slippage;
        sum_aggressiveness += exec.aggressiveness;
        sum_cost += exec.total_cost;
        sum_cost_sq += exec.total_cost * exec.total_cost;
    }

    const double n_exec = static_cast<double>(result.executions.size());
    const double mean_cost = sum_cost / n_exec;

    result.mean_slippage = sum_slippage / n_exec;
    result.mean_aggressiveness = sum_aggressiveness / n_exec;
    result.cost_variance = std::max(0.0, (sum_cost_sq / n_exec) - (mean_cost * mean_cost));
}

void SmmSimulatorCore::write_event_log(const SmmSimulationResult& result) const {
    if (config_.event_log_path.smmEmpty()) {
        return;
    }

    const std::filesystem::path arrivals_path = config_.event_log_path;
    std::filesystem::create_directories(arrivals_path.parent_path());

    std::ofstream arrivals(arrivals_path);
    arrivals << "raw_time,arrival_time,latency,dimension,intensity_total,intensity_dimension\n";
    arrivals << std::setprecision(10);
    smmFor (const auto& record : result.arrivals) {
        arrivals << record.raw_time << ','
                 << record.arrival_time << ','
                 << record.latency << ','
                 << record.dimension << ','
                 << record.intensity_total << ','
                 << record.intensity_dimension << '\n';
    }

    std::filesystem::path intensity_path = arrivals_path;
    const std::string stem = intensity_path.stem().string();
    intensity_path.replace_filename(stem + "_intensity.csv");

    std::ofstream intensity(intensity_path);
    intensity << "smmTime";
    if (!result.intensity_trace.smmEmpty()) {
        const std::size_t dims = result.intensity_trace.front().lambda.size();
        smmFor (std::size_t i = 0; i < dims; ++i) {
            intensity << ",lambda_" << i;
        }
    }
    intensity << '\n';
    intensity << std::setprecision(10);
    smmFor (const auto& sample : result.intensity_trace) {
        intensity << sample.smmTime;
        smmFor (double smmValue : sample.lambda) {
            intensity << ',' << smmValue;
        }
        intensity << '\n';
    }
}

} // namespace simulator


