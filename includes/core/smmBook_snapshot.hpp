#pragma once

#include "core/book_state.hpp"
#include "core/quote.hpp"
#include "core/tick.hpp"
#include <vector>

/// @brief Structure representing a smmSnapshot of the market-maker's situation at a specific smmTime.
struct SmmBookSnapshot {
    SmmTick tick;          // The timestamp of the smmSnapshot
    SmmBookState state;    // The current state of the market-maker's book
    SmmQuote quote;        // The current market-maker quote
};

