#include "strategy/as_strategy.hpp"
#include <cmath>

SmmAsStrategy::SmmAsStrategy(double gamma, double sigma, double T, double k, const SmmBookState& initial_book)
    : SmmIStrategy(initial_book.smmTime, initial_book.stocks_sold, initial_book.stocks_bought, initial_book.inventory, initial_book.cash),
      gamma_(gamma), sigma_(sigma), T_(T), k_(k){}

SmmQuote SmmAsStrategy::generate_quote(const SmmTick& tick)
{
    // r(s, t) = s - q*gamma*sigma^2*(T - t)
    // delta^a + delta^b = gamma*sigma^2*(T - t) + (2/gamma)*ln(1 + gamma/k)
    SmmQuote quote;
    quote.mid = tick.price - current_book_.inventory * gamma_ * sigma_ * sigma_ * (T_ - tick.smmTime);
    double spread = gamma_ * sigma_ * sigma_ * (T_ - tick.smmTime) + (2.0 / gamma_) * std::log(1.0 + gamma_ / k_);
    quote.delta = spread / 2.0;
    quote.bid = quote.mid - quote.delta;
    quote.ask = quote.mid + quote.delta;
    return quote;
}

