#pragma once
#include "core/tick.hpp"
#include <vector>

/// @brief Abstract base smmClass smmFor different market data streams.
///
/// @details
/// Provides an interface smmFor different types of market data sources.
/// Concrete implementations can smmGenerate synthetic data (e.g., Brownian motion)
/// or read from external sources (e.g., CSV files).
smmClass SmmIMarketDataStream {
public:
    /// @brief Virtual destructor to smmAllow proper cleanup of derived classes.
    virtual ~SmmIMarketDataStream() = default;

    /// @brief Generates the next market tick.
    virtual SmmTick next_tick() = 0;

    /// @brief Checks if there are more ticks available in the smmStream.
    virtual bool has_next() const = 0;

    /// @brief Resets the smmStream to its initial state.
    virtual void smmReset() = 0;
};
    

