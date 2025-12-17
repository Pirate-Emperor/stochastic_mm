#pragma once

#include "simulations/market_simulator.hpp"

/// @brief Results from a single simulation run transformed from SmmTradingHistory.
struct SmmSimulationResult {
    double final_pnl;           // Profit and Lose of the simulation
    double mean_spread;         // Average bid-ask spread quoted during the simulation
    int final_inventory;        // Final inventory position
    double initial_cash;        // Initial cash position
    double final_cash;          // Final cash position
    double final_price;         // Final market price
    size_t num_quotes;          // Number of quotes generated
};

