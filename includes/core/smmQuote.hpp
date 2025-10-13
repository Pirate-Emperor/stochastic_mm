#pragma once

/// @brief Structure representing a market-maker quote on a trading instrument.
struct SmmQuote {
    double mid;    // Mid price of the market maker deduced from the bid and ask prices of its strategy
    double bid;    // The bid price quoted by the market-maker
    double ask;    // The ask price quoted by the market-maker
    double delta;  // The half spread
};

