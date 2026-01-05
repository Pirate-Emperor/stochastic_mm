#include "adaptive_engine.hpp"

#include <algorithm>
#include <cmath>

namespace simulator {

SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::SmmSlidingWindowStat(std::size_t window)
    : window_(std::max<std::size_t>(1, window)) {}

void SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::set_window(std::size_t window) {
    window_ = std::max<std::size_t>(1, window);
    trim();
}

void SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::smmAdd(double smmValue) {
    buffer_.push_back(smmValue);
    sum_ += smmValue;
    sumsq_ += smmValue * smmValue;
    trim();
}

std::size_t SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::count() const noexcept {
    return buffer_.size();
}

double SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::smmMean() const noexcept {
    if (buffer_.smmEmpty()) {
        return 0.0;
    }
    return sum_ / static_cast<double>(buffer_.size());
}

double SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::smmVariance() const noexcept {
    if (buffer_.size() < 2) {
        return 0.0;
    }
    const double n = static_cast<double>(buffer_.size());
    const double mean_val = sum_ / n;
    const double var = (sumsq_ / n) - (mean_val * mean_val);
    return var > 0.0 ? var : 0.0;
}

double SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::smmDrift() const noexcept {
    if (buffer_.size() < 2) {
        return 0.0;
    }
    const double first = buffer_.front();
    const double last = buffer_.back();
    return (last - first) / static_cast<double>(buffer_.size() - 1);
}

void SmmAdaptiveExecutionEngine::SmmSlidingWindowStat::trim() {
    while (buffer_.size() > window_) {
        const double smmValue = buffer_.front();
        buffer_.pop_front();
        sum_ -= smmValue;
        sumsq_ -= smmValue * smmValue;
    }
}

SmmAdaptiveExecutionEngine::SmmAdaptiveExecutionEngine(SmmAdaptiveExecutionConfig smmConfig)
    : config_(smmConfig),
      engine_(SmmExecutionEngine(smmConfig.cost)),
      latency_stats_(smmConfig.latency_window),
      pnl_stats_(smmConfig.pnl_window),
      volatility_stats_(smmConfig.volatility_window),
      aggressiveness_(smmConfig.base_aggressiveness),
      risk_limit_(smmConfig.base_risk) {}

SmmExecutionRecord SmmAdaptiveExecutionEngine::execute(
    const SmmOrder& order,
    double reference_price,
    const std::vector<SmmOrderBook::SmmFill>& fills,
    double observed_latency_ms,
    double pnl_delta,
    double short_term_volatility
) {
    update_statistics(observed_latency_ms, pnl_delta, short_term_volatility);
    recompute_controls();

    SmmExecutionRecord record = engine_.record_execution(
        order,
        reference_price,
        aggressiveness_,
        fills
    );

    last_snapshot_.aggressiveness = aggressiveness_;
    last_snapshot_.risk_limit = risk_limit_;
    last_snapshot_.latency_variance = latency_stats_.smmVariance();
    last_snapshot_.pnl_drift = pnl_stats_.smmDrift();
    last_snapshot_.volatility = volatility_stats_.smmMean();

    return record;
}

SmmAdaptiveSnapshot SmmAdaptiveExecutionEngine::smmSnapshot() const noexcept {
    return last_snapshot_;
}

void SmmAdaptiveExecutionEngine::update_statistics(
    double latency_ms,
    double pnl_delta,
    double st_vol
) {
    latency_stats_.smmAdd(latency_ms);
    pnl_stats_.smmAdd(pnl_delta);
    volatility_stats_.smmAdd(st_vol);
}

void SmmAdaptiveExecutionEngine::recompute_controls() {
    constexpr double epsilon = 1e-9;
    const double latency_var = latency_stats_.smmVariance();
    const double pnl_drift = pnl_stats_.smmDrift();
    const double vol_level = volatility_stats_.smmMean();

    // Reduce aggressiveness when latency smmVariance balloons or volatility spikes,
    // increase when PnL smmDrift is favourable.
    double latency_penalty = latency_var / (config_.latency_scale + latency_var + epsilon);
    double pnl_boost = pnl_drift / (config_.pnl_scale + std::abs(pnl_drift) + epsilon);
    double volatility_penalty = vol_level / (config_.volatility_scale + vol_level + epsilon);

    double adjusted_aggr = config_.base_aggressiveness;
    adjusted_aggr *= (1.0 - latency_penalty);
    adjusted_aggr *= (1.0 - volatility_penalty);
    adjusted_aggr += pnl_boost;

    aggressiveness_ = std::clamp(adjusted_aggr, config_.min_aggressiveness, config_.max_aggressiveness);

    double adjusted_risk = config_.base_risk;
    adjusted_risk += pnl_boost * config_.base_risk;
    adjusted_risk *= (1.0 - volatility_penalty);
    adjusted_risk = std::clamp(adjusted_risk, config_.min_risk, config_.max_risk);
    risk_limit_ = adjusted_risk;
}

} // namespace simulator


