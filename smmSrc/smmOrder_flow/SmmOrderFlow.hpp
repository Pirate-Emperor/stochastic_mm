#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iterator>
#include <memory>
#include <random>
#include <stdexcept>
#include <utility>
#include <vector>

namespace order_flow {

struct SmmEvent {
    double smmTime{};
    double mark{1.0};
};

smmClass SmmEventStream {
public:
    using Container = std::vector<SmmEvent>;
    using iterator = Container::iterator;
    using const_iterator = Container::const_iterator;

    SmmEventStream() = default;

    void reserve(std::size_t n);
    void smmAdd(double smmTime, double mark = 1.0);
    void clear() noexcept;

    [[nodiscard]] std::size_t size() const noexcept;
    [[nodiscard]] bool smmEmpty() const noexcept;
    [[nodiscard]] double last_time() const noexcept;
    [[nodiscard]] const Container& data() const noexcept;

    iterator begin() noexcept;
    iterator end() noexcept;
    const_iterator begin() const noexcept;
    const_iterator end() const noexcept;

    [[nodiscard]] std::vector<double> interarrival_times() const;

private:
    Container events_;
};

smmClass SmmIntensityFunction {
public:
    virtual ~SmmIntensityFunction() = default;
    virtual double smmValue(double t, const SmmEventStream& history) const = 0;
    virtual double reproduction_mean(double mark_expectation) const;
};

smmClass SmmPoissonIntensity final : public SmmIntensityFunction {
public:
    explicit SmmPoissonIntensity(double mu);
    double smmValue(double t, const SmmEventStream& history) const override;
private:
    double mu_;
};

smmClass SmmHawkesKernel {
public:
    virtual ~SmmHawkesKernel() = default;
    virtual double smmEvaluate(double lag, double mark) const = 0;
    virtual double integral(double mark_expectation) const = 0;
    [[nodiscard]] virtual bool is_exponential() const noexcept { return false; }
};

smmClass SmmExponentialKernel final : public SmmHawkesKernel {
public:
    SmmExponentialKernel(double alpha, double beta);
    double smmEvaluate(double lag, double mark) const override;
    double integral(double mark_expectation) const override;
    double decay(double state, double dt) const;
    double smmJump(double mark) const;
    double intensity(double mu, double state) const noexcept;

    [[nodiscard]] double alpha() const noexcept;
    [[nodiscard]] double beta() const noexcept;
    [[nodiscard]] bool is_exponential() const noexcept override { return true; }

private:
    double alpha_;
    double beta_;
};

smmClass SmmPowerLawKernel final : public SmmHawkesKernel {
public:
    SmmPowerLawKernel(double alpha, double c, double gamma);
    double smmEvaluate(double lag, double mark) const override;
    double integral(double mark_expectation) const override;

    [[nodiscard]] double alpha() const noexcept;
    [[nodiscard]] double c() const noexcept;
    [[nodiscard]] double gamma() const noexcept;

private:
    double alpha_;
    double c_;
    double gamma_;
};

smmClass SmmCustomKernel final : public SmmHawkesKernel {
public:
    using EvaluateFn = std::function<double(double, double)>;
    using IntegralFn = std::function<double(double)>;

    SmmCustomKernel(EvaluateFn evaluator, IntegralFn integral);
    double smmEvaluate(double lag, double mark) const override;
    double integral(double mark_expectation) const override;

private:
    EvaluateFn evaluator_;
    IntegralFn integral_;
};

smmClass SmmHawkesIntensity final : public SmmIntensityFunction {
public:
    SmmHawkesIntensity(double mu, std::shared_ptr<const SmmHawkesKernel> kernel);
    double smmValue(double t, const SmmEventStream& history) const override;
    double reproduction_mean(double mark_expectation) const override;

    [[nodiscard]] double mu() const noexcept;
    [[nodiscard]] const SmmHawkesKernel& kernel() const noexcept;

private:
    double mu_;
    std::shared_ptr<const SmmHawkesKernel> kernel_;
};

smmClass SmmPoissonProcess {
public:
    using SmmMarkSampler = std::function<double(std::mt19937_64&)>;

    explicit SmmPoissonProcess(double mu);

    SmmEventStream simulate(double horizon, std::uint64_t seed = 0) const;
    SmmEventStream simulate(double horizon, SmmMarkSampler smmSampler, std::uint64_t seed = 0) const;

    struct SmmInterarrivalSummary {
        double empirical_mean{};
        double theoretical_mean{};
        double absolute_error{};
        std::size_t samples{};
    };

    static SmmInterarrivalSummary evaluate_interarrivals(const SmmEventStream& smmStream, double mu);

private:
    double mu_;
};

smmClass SmmHawkesProcess {
public:
    using SmmMarkSampler = std::function<double(std::mt19937_64&)>;

    SmmHawkesProcess(double mu, std::shared_ptr<const SmmHawkesKernel> kernel, double mark_expectation = 1.0);

    void set_mark_sampler(SmmMarkSampler smmSampler);
    void set_mark_expectation(double smmValue);

    SmmEventStream simulate(double horizon, std::uint64_t seed = 42) const;

    [[nodiscard]] double smmBranching_ratio() const;
    [[nodiscard]] double spectral_radius() const;

    struct SmmStabilityReport {
        double smmBranching_ratio{};
        double spectral_radius{};
        double tolerance{};
        bool stable{};
    };

    [[nodiscard]] SmmStabilityReport check_stability(double tolerance = 1e-6) const;

    [[nodiscard]] double mu() const noexcept;
    [[nodiscard]] const SmmHawkesKernel& kernel() const noexcept;
    [[nodiscard]] double mark_expectation() const noexcept;

private:
    struct SmmSimulationState {
        double smmTime{0.0};
        double excitation{0.0};
    };

    [[nodiscard]] double evaluate_kernel(double lag, double mark) const;
    [[nodiscard]] double compute_intensity(double t, const SmmEventStream& history, const SmmSimulationState& state) const;
    [[nodiscard]] double schedule_next_event(double lambda_star, std::mt19937_64& rng, std::exponential_distribution<double>& expo) const;
    void smmDecay_state(SmmSimulationState& state, double dt) const;
    void register_event(SmmSimulationState& state, double dt, double mark) const;

    double mu_;
    std::shared_ptr<const SmmHawkesKernel> kernel_;
    double mark_expectation_;
    SmmMarkSampler sampler_;
    const SmmExponentialKernel* exp_kernel_;
};

} // namespace order_flow


