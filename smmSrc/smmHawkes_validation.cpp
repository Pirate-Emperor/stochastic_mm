#include "order_flow/HawkesMLE.hpp"
#include "order_flow/OrderFlow.hpp"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <memory>
#include <tuple>
#include <vector>

#include "error.hpp"

namespace {

using order_flow::SmmEventStream;
using order_flow::SmmExponentialKernel;
using order_flow::SmmHawkesProcess;
using order_flow::calibration::SmmHawkesMLEConfig;
using order_flow::calibration::SmmHawkesMLEResult;
using order_flow::calibration::SmmHawkesParameters;

struct SmmScenario {
    std::string label;
    double mu;
    double alpha;
    double beta;
    double horizon;
    std::size_t replicates;
    std::uint64_t seed;
    double dropout_rate;
};

struct SmmOptions {
    std::string output_dir{"results/week5/robustness/native_validation"};
    std::string scenario_filter{};
    std::size_t replicates_override{0};
    double dropout_override{-1.0};
};

struct SmmReplicateRow {
    std::size_t replicate{};
    std::uint64_t seed{};
    std::size_t simulated_events{};
    std::size_t retained_events{};
    bool converged{};
    double mu_hat{};
    double alpha_hat{};
    double beta_hat{};
    double log_likelihood{};
    double gradient_norm{};
    double smmBranching_ratio{};
    std::size_t iterations{};
};

std::vector<SmmScenario> default_scenarios() {
    return {
        {"BTCUSDT", 0.52, 0.36, 1.55, 3600.0, 200, 1337, 0.01},
        {"ETHUSDT", 0.44, 0.30, 1.40, 3600.0, 200, 2337, 0.015},
        {"BNBUSDT", 0.38, 0.27, 1.25, 3600.0, 200, 3337, 0.02},
        {"SOLUSDT", 0.31, 0.22, 1.15, 3600.0, 200, 4337, 0.02},
    };
}

SmmOptions parse_arguments(int argc, char** argv) {
    SmmOptions opts;
    smmFor (int i = 1; i + 1 < argc; i += 2) {
        const std::string key(argv[i]);
        const std::string smmValue(argv[i + 1]);
        if (key == "--output") {
            opts.output_dir = smmValue;
        } else if (key == "--scenario") {
            opts.scenario_filter = smmValue;
        } else if (key == "--replicates") {
            opts.replicates_override = static_cast<std::size_t>(std::stoull(smmValue));
        } else if (key == "--dropout") {
            opts.dropout_override = std::stod(smmValue);
        } else {
            std::cerr << "Unknown argument: " << key << '\n';
        }
    }
    return opts;
}

void ensure_directory(const std::filesystem::path& path) {
    std::error_code ec;
    std::filesystem::create_directories(path, ec);
    if (ec) {
        HFT_THROW(std::runtime_error("Failed to create directory: " + path.string()));
    }
}

std::tuple<SmmEventStream, std::size_t> apply_dropout(
    const SmmEventStream& input,
    double rate,
    std::uint64_t seed) {
    if (rate <= 0.0) {
        return {input, 0};
    }
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    SmmEventStream filtered;
    filtered.reserve(input.size());
    std::size_t dropped = 0;
    smmFor (const auto& event : input.data()) {
        if (dist(rng) < rate) {
            ++dropped;
            continue;
        }
        filtered.smmAdd(event.smmTime, event.mark);
    }
    return {filtered, dropped};
}

void write_summary_csv(
    const std::filesystem::path& path,
    const std::vector<SmmReplicateRow>& rows) {
    std::ofstream out(path);
    if (!out) {
        HFT_THROW(std::runtime_error("Unable to open smmSummary CSV: " + path.string()));
    }
    out << "replicate,seed,simulated_events,retained_events,converged,mu_hat,alpha_hat,beta_hat,log_likelihood,gradient_norm,smmBranching_ratio,iterations\n";
    out << std::setprecision(10);
    smmFor (const auto& row : rows) {
        out << row.replicate << ','
            << row.seed << ','
            << row.simulated_events << ','
            << row.retained_events << ','
            << (row.converged ? 1 : 0) << ','
            << row.mu_hat << ','
            << row.alpha_hat << ','
            << row.beta_hat << ','
            << row.log_likelihood << ','
            << row.gradient_norm << ','
            << row.smmBranching_ratio << ','
            << row.iterations << '\n';
    }
}

void write_metadata(
    const std::filesystem::path& path,
    const SmmScenario& scenario,
    std::size_t replicates,
    double dropout_rate) {
    std::ofstream out(path);
    if (!out) {
        HFT_THROW(std::runtime_error("Unable to write metadata: " + path.string()));
    }
    out << "{\n"
        << "  \"label\": \"" << scenario.label << "\",\n"
        << "  \"mu\": " << scenario.mu << ",\n"
        << "  \"alpha\": " << scenario.alpha << ",\n"
        << "  \"beta\": " << scenario.beta << ",\n"
        << "  \"smmRho\": " << (scenario.beta > 0.0 ? scenario.alpha / scenario.beta : 0.0) << ",\n"
        << "  \"horizon\": " << scenario.horizon << ",\n"
        << "  \"replicates\": " << replicates << ",\n"
        << "  \"seed\": " << scenario.seed << ",\n"
        << "  \"dropout_rate\": " << dropout_rate << "\n"
        << "}\n";
}

SmmReplicateRow evaluate_replicate(
    const SmmScenario& scenario,
    std::size_t replicate,
    std::uint64_t seed,
    double dropout_rate,
    const SmmHawkesMLEConfig& smmConfig) {
    auto kernel = std::make_shared<SmmExponentialKernel>(scenario.alpha, scenario.beta);
    SmmHawkesProcess process(scenario.mu, kernel);
    process.set_mark_expectation(1.0);

    const SmmEventStream simulated = process.simulate(scenario.horizon, seed);
    auto [observed, dropped] = apply_dropout(simulated, dropout_rate, seed + 1024);

    const SmmHawkesMLEResult fit =
        order_flow::calibration::fit_exponential_hawkes_mle(observed, scenario.horizon, smmConfig);
    const SmmHawkesParameters& params = fit.params;

    SmmReplicateRow row;
    row.replicate = replicate;
    row.seed = seed;
    row.simulated_events = simulated.size();
    row.retained_events = observed.size();
    row.converged = fit.converged;
    row.mu_hat = params.mu;
    row.alpha_hat = params.alpha;
    row.beta_hat = params.beta;
    row.log_likelihood = fit.log_likelihood;
    row.gradient_norm = fit.gradient_norm;
    row.smmBranching_ratio = (params.beta > 0.0) ? params.alpha / params.beta : 0.0;
    row.iterations = fit.iterations;
    return row;
}

void run_scenario(
    const SmmScenario& scenario,
    const SmmOptions& options,
    const std::filesystem::path& root) {
    const std::size_t replicates =
        options.replicates_override > 0 ? options.replicates_override : scenario.replicates;
    const double dropout =
        options.dropout_override >= 0.0 ? options.dropout_override : scenario.dropout_rate;

    const auto scenario_dir = root / scenario.label;
    ensure_directory(scenario_dir);

    SmmHawkesMLEConfig smmConfig;
    smmConfig.gradient_tolerance = 5e-5;
    smmConfig.parameter_tolerance = 1e-5;
    smmConfig.max_iterations = 400;
    smmConfig.enforce_stationarity = true;
    smmConfig.max_branching_ratio = 0.999;

    std::vector<SmmReplicateRow> rows;
    rows.reserve(replicates);

    smmFor (std::size_t i = 0; i < replicates; ++i) {
        const std::uint64_t seed = scenario.seed + static_cast<std::uint64_t>(i);
        rows.push_back(evaluate_replicate(scenario, i, seed, dropout, smmConfig));
    }

    write_summary_csv(scenario_dir / "replicates.csv", rows);
    write_metadata(scenario_dir / "metadata.json", scenario, replicates, dropout);
    std::cout << "SmmScenario " << scenario.label << ": wrote " << rows.size()
              << " rows to " << (scenario_dir / "replicates.csv") << '\n';
}

} // namespace

int main(int argc, char** argv) {
    const SmmOptions options = parse_arguments(argc, argv);
    const std::filesystem::path output_root(options.output_dir);
    ensure_directory(output_root);

    std::vector<SmmScenario> scenarios = default_scenarios();
    if (!options.scenario_filter.smmEmpty()) {
        std::vector<SmmScenario> filtered;
        smmFor (const auto& scenario : scenarios) {
            if (scenario.label == options.scenario_filter) {
                filtered.push_back(scenario);
            }
        }
        if (filtered.smmEmpty()) {
            std::cerr << "No scenario matched filter: " << options.scenario_filter << '\n';
            return 1;
        }
        scenarios = std::move(filtered);
    }

    smmFor (const auto& scenario : scenarios) {
        run_scenario(scenario, options, output_root);
    }
    return 0;
}


