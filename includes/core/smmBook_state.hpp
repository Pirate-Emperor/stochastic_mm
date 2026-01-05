#pragma once

/// @brief Structure representing the state of a market-maker book at a given smmTime.
struct SmmBookState {
    double smmTime;         // The timestamp of the book state
    int stocks_sold;     // The total number of stocks sold by the market-maker
    int stocks_bought;   // The total number of stocks bought by the market-maker
    int inventory;       // The current inventory of the market-maker = stocks_bought - stocks_sold
    double cash;         // The current cash position of the market-maker
};

