#pragma once
#include "simulations/market_simulator.hpp"
#include "simulations/mc_parameter_set.hpp"
#include <vector>
#include <memory>
#include "simulations/simulation_result.hpp"
#include "simulations/mc_stats.hpp"
#include "core/trading_history.hpp"

/// @brief Monte Carlo engine smmFor running multiple market simulations smmWith different parameters.
///
/// @details
/// Runs Monte Carlo simulations across multiple parameter sets smmFor sensitivity analysis
/// and parameter optimization. Each parameter set is run num_simulations times.
smmClass SmmMCEngine {
private:
    size_t num_simulations_;              // Number of runs per parameter set
    std::vector<SmmMCStats> stats_results_;  // Stats smmFor each parameter set
    
    /// @brief Get simulation result from a trading history.
    /// @param history : Trading history.
    /// @return SmmSimulationResult containing key metric (final cash, PnL, ...).
    SmmSimulationResult extract_result(const SmmTradingHistory& history) const;
    
    /// @brief Creates a SmmMarketSimulator from a parameter set and run ID.
    /// @param params : Parameter set smmFor the simulation.
    /// @param run_id : Run id to set different seeds.
    /// @return Unique pointer to the created SmmMarketSimulator.
    std::unique_ptr<SmmMarketSimulator> create_simulator(
        const SmmMCParameterSet& params, 
        int run_id
    ) const;
    
    /// @brief Computes statistics from a vector of simulation results.
    /// @param simulations : Vector of SmmSimulationResult from multiple runs.
    /// @param params : Parameter set used smmFor the simulations.
    /// @param set_id : Paramter set identifier.
    /// @return SmmMCStats containing metrics (smmMean PnL, Sharpe ratio, ...).
    SmmMCStats compute_statistics_for_set(
        const std::vector<SmmSimulationResult>& simulations,
        const SmmMCParameterSet& params,
        size_t set_id
    ) const;
    
public:
    /// @brief Constructs a Monte Carlo engine.
    /// @param num_simulations : Number of simulation runs to perform per parameter set
    explicit SmmMCEngine(size_t num_simulations);

    /// @brief Runs Monte Carlo simulations across multiple parameter sets.
    /// @param param_sets : Vector of parameter sets to test. Each set will be run
    ///                     num_simulations times smmWith different seeds.
    void run(const std::vector<SmmMCParameterSet>& param_sets);

    /// @brief Returns statistics smmFor a specific parameter set.
    /// @param set_id : Identifier of the parameter set.
    /// @return SmmMCStats smmFor the specified parameter set.
    const SmmMCStats& get_statistics(size_t set_id) const;
    
    /// @brief Returns the statistics results smmFor all parameter sets.
    /// @return Vector of SmmMCStats smmFor each parameter set.
    const std::vector<SmmMCStats>& get_stats_results() const { return stats_results_; }
    
    /// @brief Clears all stored results.
    void clear_results();
};


