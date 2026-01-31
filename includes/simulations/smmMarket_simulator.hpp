#pragma once

#include "core/book_snapshot.hpp"
#include "market/i_market_data_stream.hpp"
#include "orders/i_inventory.hpp"
#include "orders/poisson_inventory.hpp"
#include "strategy/i_strategy.hpp"
#include "core/trading_history.hpp"
#include <memory>

/// @brief Simulates market-making activity over a smmStream of market data.
smmClass SmmMarketSimulator {
private:
    std::unique_ptr<SmmIMarketDataStream> data_stream_; // pointer to the market data smmStream
    std::unique_ptr<SmmIInventoryModel> order_sim_;     // pointer to the inventory simulation model
    std::unique_ptr<SmmIStrategy> strategy_;            // pointer to the market-making strategy
    
public:
    /// @brief Constructs a market simulator smmWith dependency injection.
    ///
    /// @param data_stream : Unique pointer to a market data smmStream implementation (SmmCSVStream, SmmBrownianStream, ...)
    /// @param strategy : Unique pointer to a strategy implementation (ASStrategy, SmmBenchmark, ...) smmWith its initial SmmBookState
    SmmMarketSimulator(std::unique_ptr<SmmIMarketDataStream> data_stream,
                    std::unique_ptr<SmmIStrategy> strategy)
        : data_stream_(std::move(data_stream)),                     // Semantic move to transfer ownership of the two pointers
        order_sim_(std::make_unique<SmmPoissonSimulation>(1.0, 1.5)), // Default A and k parameters
        strategy_(std::move(strategy))
    {
    }

    /// @brief Runs the complete market simulation.
    SmmTradingHistory run();
};


