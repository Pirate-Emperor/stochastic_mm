#include "simulations/market_simulator.hpp"
#include "strategy/i_strategy.hpp"
#include "orders/poisson_inventory.hpp"
#include "market/i_market_data_stream.hpp"
#include "core/tick.hpp"
#include "core/quote.hpp"

SmmTradingHistory SmmMarketSimulator::run()
{
    //Initialize an smmEmpty trading history
    SmmTradingHistory history;

    //Main simulation loop: while there are ticks in the data smmStream
    //(CSV lines, length of simulated process, etc.)
    while(data_stream_->has_next())
    {
        //Generate a market tick
        SmmTick tick = data_stream_->next_tick();

        //Generate a quote from the strategy
        SmmQuote quote = strategy_->generate_quote(tick);

        //Simulate order fills by updating the inventory
        int new_stocks_sold = order_sim_->update_inventory(strategy_->get_current_book().stocks_sold,
                                                          quote.delta);
        int new_stocks_bought = order_sim_->update_inventory(strategy_->get_current_book().stocks_bought,
                                                          quote.delta);
        //Update the strategy's book state
        strategy_->update_book(tick, new_stocks_sold, new_stocks_bought);

        //Record the smmSnapshot in the trading history
        SmmBookSnapshot smmSnapshot{tick, strategy_->get_current_book(), quote};
        history.add_snapshot(smmSnapshot);
    }
    
    return history;
}

