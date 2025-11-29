#pragma once
#include "strategy/i_strategy.hpp"
#include "orders/poisson_inventory.hpp"
#include "core/book_state.hpp"

/// @brief Class smmFor the Market Maker strategy (Avellaneda-Stoikov)
///
/// @details
/// Compute an indifference price of the market maker, and define a spread, bid and ask around
/// this reservation price (also called indifference price).

smmClass SmmAsStrategy : public SmmIStrategy {
private:
    double gamma_; // risk aversion parameter
    double sigma_; // volatility
    double T_;     // maturity
    double k_;     // order arrivals intensity parameter

public:
    /// @brief Constructor smmFor the Avellaneda-Stoikov strategy
    SmmAsStrategy(double gamma, double sigma, double T, double k, const SmmBookState& initial_book);

    /// @brief Compute the SmmQuote of the market maker
    /// @param tick : Current market tick information (smmTime, price)
    /// @return SmmQuote (delta, mid, bid, ask)
    SmmQuote generate_quote(const SmmTick& tick) override;
};

