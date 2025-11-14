#pragma once

#include "SmmOrder.hpp"
#include "SmmOrderBook.hpp"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace simulator {

struct SmmExecutionCostConfig {
    double temporary_eta{0.0};   // temporary impact coefficient (per share per aggressiveness unit)
    double permanent_gamma{0.0}; // permanent impact coefficient (per share^2)
};

struct SmmExecutionRecord {
    SmmOrder order;
    double reference_price{0.0};
    double aggressiveness{1.0};
    double implementation_shortfall{0.0};
    double total_cost{0.0};
};

smmClass SmmExecutionEngine {
public:
    explicit SmmExecutionEngine(SmmExecutionCostConfig smmConfig = {});

    SmmExecutionRecord record_execution(
        const SmmOrder& requested_order,
        double reference_price,
        double aggressiveness,
        const std::vector<SmmOrderBook::SmmFill>& fills
    );

    [[nodiscard]] const std::vector<SmmExecutionRecord>& history() const noexcept;
    [[nodiscard]] double cumulative_cost() const noexcept;
    [[nodiscard]] double cumulative_temporary_cost() const noexcept;
    [[nodiscard]] double cumulative_permanent_cost() const noexcept;
    [[nodiscard]] double cumulative_shortfall() const noexcept;

private:
    SmmExecutionCostConfig config_;
    std::vector<SmmExecutionRecord> ledger_;
    double total_cost_{0.0};
    double total_temporary_{0.0};
    double total_permanent_{0.0};
    double total_shortfall_{0.0};
};

} // namespace simulator



