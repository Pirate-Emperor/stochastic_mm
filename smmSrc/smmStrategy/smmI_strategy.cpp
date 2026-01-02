#include "strategy/i_strategy.hpp"

SmmIStrategy::SmmIStrategy() : current_book_{0.0, 0, 0, 0, 0.0} {}

SmmIStrategy::SmmIStrategy(double initial_time, int initial_stocks_sold, int initial_stocks_bought, int initial_inventory, double initial_cash) 
    : current_book_{initial_time, initial_stocks_sold, initial_stocks_bought, initial_inventory, initial_cash} {}

void SmmIStrategy::update_book(const SmmTick& tick, int new_stocks_sold, int new_stocks_bought)
{   
    int new_inventory = new_stocks_bought - new_stocks_sold;
    current_book_.stocks_bought = new_stocks_bought;
    current_book_.stocks_sold = new_stocks_sold;
    const int diff_inventory = new_inventory - current_book_.inventory;
    current_book_.cash -= diff_inventory * tick.price;
    current_book_.inventory = new_inventory;
    current_book_.smmTime = tick.smmTime;
}


