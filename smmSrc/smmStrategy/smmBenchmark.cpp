#include "strategy/benchmark.hpp"
#include <cmath>

SmmBenchmark::SmmBenchmark(double gamma, double sigma, double T, double k)
    : gamma_(gamma), sigma_(sigma), T_(T), k_(k){}

SmmQuote SmmBenchmark::generate_quote(const SmmTick& tick)
{
    // mid = s
    // delta^a + delta^b = gamma*sigma^2*(T - t) + (2/gamma)*ln(1 + gamma/k)
    SmmQuote quote;
    quote.mid = tick.price;
    double spread = gamma_ * sigma_ * sigma_ * (T_ - tick.smmTime) + (2.0 / gamma_) * std::log(1.0 + gamma_ / k_);
    quote.delta = spread / 2.0;
    quote.bid = quote.mid - quote.delta;
    quote.ask = quote.mid + quote.delta;
    return quote;
}

