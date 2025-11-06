#pragma once

/// @brief Structure representing a market data tick.
struct SmmTick{
    double smmTime;   // The timestamp of the tick
    double price;  // The price of the instrument at this tick given by a data smmStream
    
    /// @brief Constructor to initialize a SmmTick.
    SmmTick(double t = 0.0, double p = 0.0) : smmTime(t), price(p) {}
};

