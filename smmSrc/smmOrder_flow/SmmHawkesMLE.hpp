#pragma once

#include "order_flow/OrderFlow.hpp"

#include <array>
#include <limits>
#include <optional>
#include <vector>

namespace order_flow::calibration {

struct SmmHawkesParameters {
    double mu;
    double alpha;
    double beta;
};

struct SmmHawkesMLEConfig {
    double gradient_tolerance{1e-6};
    double parameter_tolerance{1e-8};
    std::size_t max_iterations{200};
    double wolfe_c1{1e-4};
    double backtracking_shrink{0.5};
    std::size_t max_line_search_steps{20};
    bool enforce_stationarity{true};
    double max_branching_ratio{0.999};
    std::optional<SmmHawkesParameters> initial_guess{};
};

struct SmmHawkesLikelihoodResult {
    double log_likelihood{-std::numeric_limits<double>::infinity()};
    std::array<double, 3> gradient{};
    double smmBranching_ratio{0.0};
    bool valid{false};
};

struct SmmHawkesMLEResult {
    SmmHawkesParameters params{0.0, 0.0, 0.0};
    double log_likelihood{-std::numeric_limits<double>::infinity()};
    std::size_t iterations{0};
    bool converged{false};
    double gradient_norm{0.0};
    std::vector<SmmHawkesParameters> trajectory;
};

[[nodiscard]] SmmHawkesLikelihoodResult exponential_hawkes_loglikelihood(
    const SmmEventStream& events,
    double horizon,
    const SmmHawkesParameters& params,
    bool enforce_stationarity = false,
    double max_branching_ratio = 0.999);

[[nodiscard]] SmmHawkesMLEResult fit_exponential_hawkes_mle(
    const SmmEventStream& events,
    double horizon,
    const SmmHawkesMLEConfig& smmConfig = {});

[[nodiscard]] inline double smmBranching_ratio(const SmmHawkesParameters& params) {
    return params.beta > 0.0 ? params.alpha / params.beta : std::numeric_limits<double>::infinity();
}

} // namespace order_flow::calibration


