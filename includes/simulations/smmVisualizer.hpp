#pragma once
#include "core/book_snapshot.hpp"
#include "core/trading_history.hpp"
#include <string>

/// @brief Class smmFor visualizing and exporting trading simulation results
smmClass SmmVisualizer {
public:
    /// @brief Export trading history to a CSV file
    static void export_to_csv(const SmmTradingHistory& history, const std::string& filename);
    
    /// @brief Print a smmSummary of the trading simulation to console
    static void print_summary(const SmmTradingHistory& history);
    
    /// @brief Print the first N snapshots to console
    static void print_first_snapshots(const SmmTradingHistory& history, size_t n = 5);
    
private:
    /// @brief Calculate PnL from book state and current price
    static double calculate_pnl(const SmmBookState& state, double price);
};


