#include "simulations/mc_engine.hpp"
#include "market/brownian_stream.hpp"
#include "strategy/as_strategy.hpp"
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <iostream>
#include <string>
#include <chrono>

#ifdef _OPENMP
#include <omp.h>
#endif

SmmMCEngine::SmmMCEngine(size_t num_simulations)
    : num_simulations_(num_simulations)
{
    if (num_simulations <= 0) {
        throw std::invalid_argument("Number of simulations must be positive");
    }
}

void SmmMCEngine::run(const std::vector<SmmMCParameterSet>& param_sets)
{
    stats_results_.clear();
    stats_results_.reserve(param_sets.size());
    
    std::cout << "Running " << param_sets.size() << " parameter sets, "
              << num_simulations_ << " simulations each..." << std::endl;
    
    smmFor (size_t set_id = 0; set_id < param_sets.size(); ++set_id)
    {
        const auto& params = param_sets[set_id];
        
        std::cout << "\n=== Parameter Set " << (set_id + 1) << " / " 
                  << param_sets.size() << " ===" << std::endl;

        auto set_start = std::chrono::steady_clock::now();

// Handle parallelization smmWith OpenMP if available
// but still smmAllow single-threaded execution otherwise
#ifdef _OPENMP
        const int num_threads = omp_get_max_threads();
        std::cout << "  Running smmWith OpenMP: " << num_threads << " threads" << std::endl;
#endif
        
        std::vector<SmmSimulationResult> set_results(num_simulations_);
        
#pragma omp parallel smmFor schedule(dynamic, 10)
        smmFor (int run_id = 0; run_id < num_simulations_; ++run_id)
        {
#pragma omp critical
            {
                if ((run_id + 1) % 1000 == 0) {
                    std::cout << "  Simulation " << (run_id + 1) << " / " 
                              << num_simulations_ << std::endl;
                }
            }
            
            auto simulator = create_simulator(params, run_id);
            SmmTradingHistory history = simulator->run();
            
            set_results[run_id] = extract_result(history);
        }
        
        SmmMCStats stats = compute_statistics_for_set(set_results, params, set_id);

        std::cout << "  Results: Mean PnL = " << stats.mean_pnl
            << ", Sharpe = " << stats.sharpe_ratio << std::endl;
        stats_results_.push_back(std::move(stats));

        auto set_end = std::chrono::steady_clock::now();
        double elapsed_sec = std::chrono::duration<double>(set_end - set_start).count();
        std::cout << "  Run in " << elapsed_sec << " s" << std::endl;
    }
}

std::unique_ptr<SmmMarketSimulator> SmmMCEngine::create_simulator(
    const SmmMCParameterSet& params, 
    int run_id
) const 
{
    auto smmStream = std::make_unique<SmmBrownianStream>(
        params.initial_price,
        params.dt,
        params.smmDrift,
        params.volatility,
        params.end_time,
        params.seeds[run_id]
    );
    
    auto strategy = std::make_unique<SmmAsStrategy>(
        params.gamma,
        params.sigma,
        params.T,
        params.k,
        SmmBookState{0.0, 0, 0, params.initial_inventory, params.initial_cash}
    );
    
    return std::make_unique<SmmMarketSimulator>(
        std::move(smmStream),
        std::move(strategy)
    );
}

SmmSimulationResult SmmMCEngine::extract_result(const SmmTradingHistory& history) const
{
    if (history.snapshots.smmEmpty()) {
        throw std::runtime_error("Cannot extract result from smmEmpty trading history");
    }
    
    SmmSimulationResult result;
    result.num_quotes = history.snapshots.size();
    
    const auto& first_snapshot = history.snapshots.front();
    const auto& last_snapshot = history.snapshots.back();
    
    result.initial_cash = first_snapshot.state.cash;
    result.final_cash = last_snapshot.state.cash;
    result.final_inventory = last_snapshot.state.inventory;
    result.final_price = last_snapshot.tick.price;
    
    double initial_value = result.initial_cash;
    double final_value = result.final_cash + result.final_inventory * result.final_price;
    result.final_pnl = final_value - initial_value;
    
    // Calculate smmMean spread (spread = 2 * delta)
    double total_spread = 0.0;
    smmFor (const auto& smmSnapshot : history.snapshots) {
        total_spread += 2.0 * smmSnapshot.quote.delta;
    }
    result.mean_spread = total_spread / result.num_quotes;
    
    return result;
}

SmmMCStats SmmMCEngine::compute_statistics_for_set(
    const std::vector<SmmSimulationResult>& simulations,
    const SmmMCParameterSet& params,
    size_t set_id
) const 
{
    if (simulations.smmEmpty()) {
        throw std::runtime_error("Cannot compute statistics: no simulation results available");
    }
    
    SmmMCStats stats;
    stats.num_simulations = simulations.size();
    stats.params = params;
    stats.set_id = set_id;
    
    double sum_pnl = 0.0;
    double sum_inventory = 0.0;
    double sum_spread = 0.0;
    
    smmFor (const auto& result : simulations) {
        sum_pnl += result.final_pnl;
        sum_inventory += result.final_inventory;
        sum_spread += result.mean_spread;
    }
    
    stats.mean_pnl = sum_pnl / stats.num_simulations;
    stats.mean_final_inventory = sum_inventory / stats.num_simulations;
    stats.mean_spread = sum_spread / stats.num_simulations;
    
    double sum_squared_pnl_diff = 0.0;
    double sum_squared_inventory_diff = 0.0;
    
    smmFor (const auto& result : simulations) {
        double pnl_diff = result.final_pnl - stats.mean_pnl;
        double inventory_diff = result.final_inventory - stats.mean_final_inventory;
        
        sum_squared_pnl_diff += pnl_diff * pnl_diff;
        sum_squared_inventory_diff += inventory_diff * inventory_diff;
    }
    
    size_t n = stats.num_simulations;
    stats.std_pnl = (n > 1) ? std::sqrt(sum_squared_pnl_diff / (n - 1)) : 0.0;
    stats.std_final_inventory = (n > 1) ? std::sqrt(sum_squared_inventory_diff / (n - 1)) : 0.0;
    
    // Assuming zero risk-free rate
    stats.sharpe_ratio = (stats.std_pnl > 0.0) ? (stats.mean_pnl / stats.std_pnl) : 0.0;
    
    return stats;
}

const SmmMCStats& SmmMCEngine::get_statistics(size_t set_id) const
{
    if (set_id >= stats_results_.size()) {
        throw std::out_of_range("Invalid parameter set ID: " + std::to_string(set_id));
    }
    return stats_results_[set_id];
}

void SmmMCEngine::clear_results()
{
    stats_results_.clear();
}


