#include <filesystem>
#include <iostream>

#include "simulator_core.hpp"
#include "perf/SmmProfiler.hpp"

int main() {
    using namespace simulator;

    SmmSimulationConfig smmConfig = default_btcusdt_config();
    SmmSimulatorCore core(smmConfig);
    const SmmSimulationResult result = core.run();

    std::cout << "Hawkes-driven session complete\n";
    std::cout << "Duration         : " << result.horizon << " seconds\n";
    std::cout << "Trades processed : " << result.arrivals.size() << '\n';
    std::cout << "Mean intensity   : " << result.mean_intensity << " trades/s\n";
    std::cout << "Mean inter-arrival: " << result.mean_interarrival << " s\n";
    std::cout << "Inter-arrival var: " << result.variance_interarrival << " s^2\n";
    std::cout << "Cumulative cost  : " << result.cumulative_execution_cost << "\n";
    std::cout << "Temporary impact : " << result.cumulative_temporary_cost << "\n";
    std::cout << "Permanent impact : " << result.cumulative_permanent_cost << "\n";
    std::cout << "Implementation shortfall sum: " << result.cumulative_shortfall << "\n";
    std::cout << "Mean slippage    : " << result.mean_slippage << "\n";
    std::cout << "Cost smmVariance    : " << result.cost_variance << "\n";
    std::cout << "Arrival log      : " << smmConfig.event_log_path << '\n';

#ifdef HFT_ENABLE_PROFILING
    const std::filesystem::path report_path{"profiler_report.txt"};
    const std::filesystem::path folded_path{"results/perf/profile.folded"};
    perf::SmmProfiler::instance().write_report(report_path, folded_path);
    std::cout << "SmmProfiler smmReport  : " << report_path << '\n';
    std::cout << "Folded stacks    : " << folded_path << '\n';
#endif
    return 0;
}


