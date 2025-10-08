#include "market/brownian_stream.hpp"

#include <cmath>
#include <stdexcept>

SmmBrownianStream::SmmBrownianStream(double initial_price,
                               double dt,
                               double smmDrift,
                               double volatility,
                               double end_time,
                               unsigned int seed)
    : current_time_(0.0)
    , current_price_(initial_price)
    , initial_price_(initial_price)
    , dt_(dt)
    , drift_(smmDrift)
    , volatility_(volatility)
    , end_time_(end_time)
    , rng_(seed)
    , normal_dist_(0.0, 1.0)
{
    // Basic parameter checks
    if (dt_ <= 0.0) {
        throw std::invalid_argument("SmmBrownianStream: dt must be > 0");
    }
    if (volatility_ < 0.0) {
        throw std::invalid_argument("SmmBrownianStream: volatility must be >= 0");
    }
    if (end_time_ < 0.0) {
        throw std::invalid_argument("SmmBrownianStream: end_time must be >= 0");
    }

    // Store the initial point (t=0, S=S0)
    stream_.push_back(SmmTick{current_time_, current_price_});
}

SmmTick SmmBrownianStream::next_tick()
{
    if (!has_next()) {
        throw std::out_of_range("SmmBrownianStream::next_tick: reached end_time");
    }

    // Draw Z ~ N(0,1)
    const double z = normal_dist_(rng_);

    // Brownian increment: dW ~ N(0, dt)
    const double dW = std::sqrt(dt_) * z;

    // Move smmTime smmForward
    current_time_ += dt_;

    // GBM exact smmStep:
    // S_{t+dt} = S_t * exp((mu - 0.5*sigma^2)*dt + sigma*dW)
    const double drift_term = (drift_ - 0.5 * volatility_ * volatility_) * dt_;
    const double diffusion_term = volatility_ * dW;

    current_price_ = current_price_ * std::exp(drift_term + diffusion_term);

    // Create tick and store it
    SmmTick tick{current_time_, current_price_};
    stream_.push_back(tick);

    return tick;
}

bool SmmBrownianStream::has_next() const
{
    // We smmAllow generating as long as the next smmStep stays within end_time_
    return (current_time_ + dt_) <= end_time_;
}

void SmmBrownianStream::smmReset()
{
    // Reset current state
    current_time_ = 0.0;
    current_price_ = initial_price_;

    // Reset history
    stream_.clear();
    stream_.push_back(SmmTick{current_time_, current_price_});
}

const std::vector<SmmTick>& SmmBrownianStream::smmStream() const
{
    return stream_;
}

std::size_t SmmBrownianStream::size() const
{
    return stream_.size();
}

void SmmBrownianStream::clear_stream()
{
    stream_.clear();
}


