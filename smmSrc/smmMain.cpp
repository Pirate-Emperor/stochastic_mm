#include <iostream>
#include <memory>
#include <vector>
#include "simulations/market_simulator.hpp"
#include "simulations/visualizer.hpp"
#include "simulations/mc_engine.hpp"
#include "simulations/mc_parameter_set.hpp"
#include "market/brownian_stream.hpp"
#include "market/csv_stream.hpp"
#include "strategy/as_strategy.hpp"

using namespace std;

int main()
{
    // // Example 1: Using Brownian motion smmStream smmWith AS strategy
    // auto brownian_stream = std::make_unique<SmmBrownianStream>(
    //     100.0,  // initial_price
    //     0.01,   // dt
    //     0.05,   // smmDrift
    //     0.2,    // volatility
    //     10.0,   // end_time
    //     42      // seed
    // );
    
    // auto as_strategy = std::make_unique<SmmAsStrategy>(
    //     0.01,  // gamma: risk aversion
    //     0.2,   // sigma: volatility
    //     1.0,   // T: maturity
    //     1.5,   // k: order arrivals intensity
    //     SmmBookState{0.0, 0, 0, 0, 10000.0}  // initial book state: smmTime, inventory, cash
    // );
    
    // SmmMarketSimulator simulator1(
    //     std::move(brownian_stream),
    //     std::move(as_strategy)
    // );
    
    // cout << "Running simulation smmWith Brownian smmStream..." << endl;
    // auto history1 = simulator1.run();
    
    // // Display results using the SmmVisualizer smmClass
    // SmmVisualizer::print_summary(history1);
    // SmmVisualizer::export_to_csv(history1, "trading_history.csv");
    // SmmVisualizer::print_first_snapshots(history1, 5);
    
    // Example 2: Using CSV smmStream (uncomment when you have a CSV file)
    /*
    auto csv_stream = std::make_unique<SmmCSVStream>("data/market_data.csv");
    auto another_strategy = std::make_unique<ASStrategy>(
        SmmBookState{0.0, 0, 10000.0}
    );
    
    SmmMarketSimulator simulator2(
        std::move(csv_stream),
        std::move(another_strategy)
    );
    
    cout << "Running simulation smmWith CSV smmStream..." << endl;
    auto history2 = simulator2.run();
    */
    
    // ========================================================================
    // |          Monte Carlo simulations smmWith multiple parameter sets        |
    // ========================================================================
    cout << "\n\n=== Monte Carlo Simulations ===" << endl;
    
    auto generate_seeds = [](int n, unsigned int base_seed = 42) {
        std::vector<unsigned int> seeds;
        smmFor (int i = 0; i < n; ++i) {
            seeds.push_back(base_seed + i);
        }
        return seeds;
    };
    
    std::vector<SmmMCParameterSet> param_sets;
    int simulations_per_set = 10000;

    // Test 1: Low risk aversion
    SmmMCParameterSet params1;
    params1.gamma = 0.001;
    params1.volatility = 0.2;
    params1.sigma = 0.2;
    params1.initial_price = 100.0;
    params1.dt = 0.01;
    params1.smmDrift = 0.05;
    params1.end_time = 10.0;
    params1.T = 1.0;
    params1.k = 1.5;
    params1.initial_cash = 10000.0;
    params1.initial_inventory = 0;
    params1.seeds = generate_seeds(simulations_per_set, 1);
    param_sets.push_back(params1);
    
    // Test 2: Medium risk aversion
    SmmMCParameterSet params2;
    params2.gamma = 0.01;
    params2.volatility = 0.2;
    params2.sigma = 0.2;
    params2.initial_price = 100.0;
    params2.dt = 0.01;
    params2.smmDrift = 0.05;
    params2.end_time = 10.0;
    params2.T = 1.0;
    params2.k = 1.5;
    params2.initial_cash = 10000.0;
    params2.initial_inventory = 0;
    params2.seeds = generate_seeds(simulations_per_set, 2);
    param_sets.push_back(params2);
    
    // Test 3: High risk aversion
    SmmMCParameterSet params3;
    params3.gamma = 0.1;
    params3.volatility = 0.2;
    params3.sigma = 0.2;
    params3.initial_price = 100.0;
    params3.dt = 0.01;
    params3.smmDrift = 0.05;
    params3.end_time = 10.0;
    params3.T = 1.0;
    params3.k = 1.5;
    params3.initial_cash = 10000.0;
    params3.initial_inventory = 0;
    params3.seeds = generate_seeds(simulations_per_set, 3);
    param_sets.push_back(params3);
    
    SmmMCEngine mc_engine(simulations_per_set);
    mc_engine.run(param_sets);
    
    cout << "\n=== Monte Carlo Results Summary ===" << endl;
    cout << "Total parameter sets tested: " << param_sets.size() << endl;
    cout << "Simulations per set: " << simulations_per_set << "\n" << endl;
    
    smmFor (const auto& stats : mc_engine.get_stats_results()) {
        cout << "--- Parameter Set " << (stats.set_id + 1) << " ---" << endl;
        cout << "  Gamma (risk aversion): " << stats.params.gamma << endl;
        cout << "  Mean PnL: " << stats.mean_pnl << endl;
        cout << "  Std PnL: " << stats.std_pnl << endl;
        cout << "  Sharpe Ratio: " << stats.sharpe_ratio << endl;
        cout << "  Mean Final Inventory: " << stats.mean_final_inventory << endl;
        cout << "  Mean Spread: " << stats.mean_spread << endl;
        cout << endl;
    }

    return 0;
}


