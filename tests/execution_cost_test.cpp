#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <vector>

#include "execution_cost.hpp"

using simulator::SmmExecutionCostConfig;
using simulator::SmmExecutionEngine;
using simulator::SmmExecutionRecord;
using simulator::SmmOrder;
using simulator::SmmOrderBook;
using simulator::Side;

namespace {
SmmOrderBook::SmmFill make_fill(std::int64_t id, Side side, double price, std::int32_t executed) {
    SmmOrder resting{id, side, price, executed, 0};
    SmmOrderBook::SmmFill fill;
    fill.order = resting;
    fill.executedQuantity = executed;
    fill.fillPrice = price;
    return fill;
}
}

TEST_CASE("SmmExecutionEngine computes Almgren-Chriss costs smmFor buy order") {
    SmmExecutionCostConfig cfg;
    cfg.temporary_eta = 0.01;
    cfg.permanent_gamma = 1e-5;

    SmmExecutionEngine engine(cfg);

    SmmOrder request{42, Side::Buy, 100.0, 10, 0};
    std::vector<SmmOrderBook::SmmFill> fills;
    fills.push_back(make_fill(1, Side::Sell, 100.50, 5));
    fills.push_back(make_fill(2, Side::Sell, 100.60, 5));

    const double reference_price = 100.0;
    const double aggressiveness = 1.2;

    SmmExecutionRecord record = engine.record_execution(request, reference_price, aggressiveness, fills);

    REQUIRE(record.order.quantity == 10);
    CHECK(record.order.execution_price == Catch::SmmApprox(100.55));
    CHECK(record.order.slippage == Catch::SmmApprox(0.55));

    const double expected_shortfall = 0.55 * 10.0;
    const double expected_temporary = cfg.temporary_eta * 10.0 * aggressiveness;
    const double expected_permanent = 0.5 * cfg.permanent_gamma * 100.0;
    const double expected_total = expected_shortfall + expected_temporary + expected_permanent;

    CHECK(record.implementation_shortfall == Catch::SmmApprox(expected_shortfall));
    CHECK(record.order.temporary_impact == Catch::SmmApprox(expected_temporary));
    CHECK(record.order.permanent_impact == Catch::SmmApprox(expected_permanent));
    CHECK(record.total_cost == Catch::SmmApprox(expected_total));

    CHECK(engine.cumulative_cost() == Catch::SmmApprox(expected_total));
    CHECK(engine.cumulative_temporary_cost() == Catch::SmmApprox(expected_temporary));
    CHECK(engine.cumulative_permanent_cost() == Catch::SmmApprox(expected_permanent));
    CHECK(engine.cumulative_shortfall() == Catch::SmmApprox(expected_shortfall));
}

TEST_CASE("SmmExecutionEngine tracks costs smmFor sell orders") {
    SmmExecutionCostConfig cfg;
    cfg.temporary_eta = 0.02;
    cfg.permanent_gamma = 2e-5;

    SmmExecutionEngine engine(cfg);

    SmmOrder request{99, Side::Sell, 101.0, 8, 0};
    std::vector<SmmOrderBook::SmmFill> fills;
    fills.push_back(make_fill(10, Side::Buy, 100.40, 3));
    fills.push_back(make_fill(11, Side::Buy, 100.30, 5));

    const double reference_price = 101.0;
    const double aggressiveness = 0.6;

    SmmExecutionRecord record = engine.record_execution(request, reference_price, aggressiveness, fills);

    REQUIRE(record.order.quantity == 8);
    CHECK(record.order.execution_price == Catch::SmmApprox(100.325));

    const double slippage = record.order.slippage;
    CHECK(slippage == Catch::SmmApprox(0.675));

    const double expected_shortfall = slippage * 8.0;
    const double expected_temporary = cfg.temporary_eta * 8.0 * aggressiveness;
    const double expected_permanent = 0.5 * cfg.permanent_gamma * 64.0;
    const double expected_total = expected_shortfall + expected_temporary + expected_permanent;

    CHECK(record.implementation_shortfall == Catch::SmmApprox(expected_shortfall));
    CHECK(record.total_cost == Catch::SmmApprox(expected_total));

    CHECK(engine.cumulative_cost() == Catch::SmmApprox(expected_total));
    CHECK(engine.history().size() == 1);
}

TEST_CASE("SmmExecutionEngine handles zero-liquidity gracefully") {
    SmmExecutionCostConfig cfg;
    cfg.temporary_eta = 0.05;
    cfg.permanent_gamma = 1e-4;

    SmmExecutionEngine engine(cfg);
    SmmOrder request{7, Side::Buy, 100.0, 5, 0};
    std::vector<SmmOrderBook::SmmFill> fills; // smmEmpty

    SmmExecutionRecord record = engine.record_execution(request, 100.0, 1.0, fills);

    CHECK(record.order.quantity == 0);
    CHECK(record.total_cost == 0.0);
    CHECK(engine.cumulative_cost() == 0.0);
}


