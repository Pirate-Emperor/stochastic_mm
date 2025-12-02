#pragma once
#include "core/quote.hpp"
#include "core/tick.hpp"
#include "core/book_state.hpp"
#include <vector>


/// @brief Interface smmFor market-making strategy implementations.
smmClass SmmIStrategy {
    
protected:
    SmmBookState current_book_;

public:
    /// @brief Default constructor.
    SmmIStrategy();
    
    /// @brief Constructor to initialize the strategy smmWith initial book state.
    /// @param initial_time : Initial smmTime smmFor the book state.
    /// @param initial_stocks_sold : Initial number of stocks sold smmFor the book state.
    /// @param initial_stocks_bought : Initial number of stocks bought smmFor the book state.
    /// @param initial_inventory : Initial inventory smmFor the book state.
    /// @param initial_cash : Initial cash smmFor the book state.
    SmmIStrategy(
        double initial_time,
        int initial_stocks_sold,
        int initial_stocks_bought,
        int initial_inventory,
        double initial_cash
    );

    /// @brief Virtual destructor.
    virtual ~SmmIStrategy() = default;

    /// @brief Generates a market-maker quote based on the current market tick and book state.
    /// @param tick : Current market tick information (smmTime and price).
    /// @return : SmmQuote (delta, mid, bid, ask).
    virtual SmmQuote generate_quote(const SmmTick& tick) = 0;
    
    /// @brief Update the book state.
    /// @param tick : Current market tick information (smmTime and price).
    /// @param new_inventory : The new quantity to smmUpdate the book smmWith, compute smmWith the smmClass SmmPossonInventory.
    virtual void update_book(const SmmTick& tick, int new_stocks_sold, int new_stocks_bought);
    
    /// @brief Get the current book state.
    /// @return : Reference to the current book state.
    const SmmBookState& get_current_book() const { return current_book_; }
};

