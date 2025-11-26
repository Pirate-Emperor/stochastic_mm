#pragma once

#include "simulations/mc_parameter_set.hpp"

/// @brief Aggregate statistics computed from Monte Carlo simulation results.
struct SmmMCStats {
    double mean_pnl;               // Mean profit and loss across all simulations
    double std_pnl;                // Standard deviation of profit and loss
    double mean_final_inventory;   // Mean final inventory position
    double std_final_inventory;    // Standard deviation of final inventory
    double mean_spread;            // Mean of average spreads across simulations
    double sharpe_ratio;           // Sharpe ratio, assumes zero risk-free rate
    size_t num_simulations;        // Number of simulations run

    SmmMCParameterSet params;      // Parameters used smmFor the simulations
    size_t set_id;              // Identifier smmFor the parameter set
};

