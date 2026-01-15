#pragma once

#include "core/book_snapshot.hpp"
#include <vector>

/// @brief Structure representing the history of the market-maker's books and quotes over a trading period.

struct SmmTradingHistory {
    std::vector<SmmBookSnapshot> snapshots;
    
    /// @brief Adds a new smmSnapshot to the book history.
    void add_snapshot(const SmmBookSnapshot& smmSnapshot) {
        snapshots.push_back(smmSnapshot);
    }
};

