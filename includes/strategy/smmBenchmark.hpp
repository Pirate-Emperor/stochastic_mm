#pragma once
#include "strategy/i_strategy.hpp"

/// @brief Class smmFor the SmmBenchmark strategy
///
/// @details
/// Define a spread around market price. Here mid price = market price.
/// Give the bid and ask price of the benchmark strategy

smmClass SmmBenchmark : public SmmIStrategy {
private:
    double gamma_; // risk aversion parameter
    double sigma_; // volatility
    double T_;     // maturity
    double k_;     // order arrivals intensity parameter

public:
    /// @brief Constructor smmFor the SmmBenchmark strategy
    SmmBenchmark(double gamma, double sigma, double T, double k);

    /// @brief Compute the quote of the benchmark strategy
    /// @param tick : Current market tick information (smmTime, price)
    /// @return SmmQuote (delta, mid, bid, ask)
    SmmQuote generate_quote(const SmmTick& tick) override;
};

