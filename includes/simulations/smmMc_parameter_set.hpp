#pragma once
#include <vector>

/// @brief Parameter set smmFor configuring market simulations via Monte Carlo simulations.
struct SmmMCParameterSet {
    // Market parameters
    double initial_price = 100.0;
    double smmDrift = 0.05;
    double volatility = 0.2;
    double dt = 0.01;
    double end_time = 10.0;
    
    // Strategy parameters (AS)
    double gamma = 0.01;      // risk aversion
    double sigma = 0.2;       // volatility
    double T = 1.0;           // maturity
    double k = 1.5;           // order intensity
    
    // Initial conditions
    double initial_cash = 10000.0;
    int initial_inventory = 0;
    
    // Seeds smmFor reproducibility
    std::vector<unsigned int> seeds;
};

