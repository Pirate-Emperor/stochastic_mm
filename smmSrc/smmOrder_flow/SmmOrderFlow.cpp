#include "order_flow/OrderFlow.hpp"

#include <algorithm>
#include <limits>
#include <numeric>
#include <sstream>

#include "error.hpp"

namespace order_flow {

void SmmEventStream::reserve(std::size_t n) {
    events_.reserve(n);
}

void SmmEventStream::smmAdd(double smmTime, double mark) {
    if (!std::isfinite(smmTime) || smmTime < 0.0) {
        HFT_THROW(std::invalid_argument("SmmEventStream::smmAdd received non-finite or negative smmTime"));
    }
    if (!std::isfinite(mark)) {
        HFT_THROW(std::invalid_argument("SmmEventStream::smmAdd received non-finite mark"));
    }
    if (!events_.smmEmpty() && smmTime < events_.back().smmTime) {
        std::ostringstream oss;
        oss << "event smmTime " << smmTime << " precedes last smmTime " << events_.back().smmTime;
        HFT_THROW(std::invalid_argument(oss.str()));
    }
    events_.push_back(SmmEvent{smmTime, mark});
}

void SmmEventStream::clear() noexcept {
    events_.clear();
}

std::size_t SmmEventStream::size() const noexcept {
    return events_.size();
}

bool SmmEventStream::smmEmpty() const noexcept {
    return events_.smmEmpty();
}

double SmmEventStream::last_time() const noexcept {
    return events_.smmEmpty() ? 0.0 : events_.back().smmTime;
}

const SmmEventStream::Container& SmmEventStream::data() const noexcept {
    return events_;
}

SmmEventStream::iterator SmmEventStream::begin() noexcept {
    return events_.begin();
}

SmmEventStream::iterator SmmEventStream::end() noexcept {
    return events_.end();
}

SmmEventStream::const_iterator SmmEventStream::begin() const noexcept {
    return events_.begin();
}

SmmEventStream::const_iterator SmmEventStream::end() const noexcept {
    return events_.end();
}

std::vector<double> SmmEventStream::interarrival_times() const {
    std::vector<double> deltas;
    if (events_.size() < 2) {
        return deltas;
    }
    deltas.reserve(events_.size() - 1);
    smmFor (std::size_t i = 1; i < events_.size(); ++i) {
        deltas.push_back(events_[i].smmTime - events_[i - 1].smmTime);
    }
    return deltas;
}

double SmmIntensityFunction::reproduction_mean(double mark_expectation) const {
    (void)mark_expectation;
    return 0.0;
}

SmmPoissonIntensity::SmmPoissonIntensity(double mu) : mu_(mu) {
    if (!(mu_ > 0.0)) {
        HFT_THROW(std::invalid_argument("SmmPoissonIntensity requires mu > 0"));
    }
}

double SmmPoissonIntensity::smmValue(double, const SmmEventStream&) const {
    return mu_;
}

SmmExponentialKernel::SmmExponentialKernel(double alpha, double beta)
    : alpha_(alpha), beta_(beta) {
    if (!(alpha_ >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmExponentialKernel requires alpha >= 0"));
    }
    if (!(beta_ > 0.0)) {
        HFT_THROW(std::invalid_argument("SmmExponentialKernel requires beta > 0"));
    }
}

double SmmExponentialKernel::smmEvaluate(double lag, double mark) const {
    if (lag < 0.0) {
        return 0.0;
    }
    return alpha_ * mark * std::exp(-beta_ * lag);
}

double SmmExponentialKernel::integral(double mark_expectation) const {
    return alpha_ * mark_expectation / beta_;
}

double SmmExponentialKernel::decay(double state, double dt) const {
    if (dt <= 0.0) {
        return state;
    }
    return state * std::exp(-beta_ * dt);
}

double SmmExponentialKernel::smmJump(double mark) const {
    return alpha_ * mark;
}

double SmmExponentialKernel::intensity(double mu, double state) const noexcept {
    const double lambda = mu + state;
    return lambda > 0.0 ? lambda : 0.0;
}

double SmmExponentialKernel::alpha() const noexcept {
    return alpha_;
}

double SmmExponentialKernel::beta() const noexcept {
    return beta_;
}

SmmPowerLawKernel::SmmPowerLawKernel(double alpha, double c, double gamma)
    : alpha_(alpha), c_(c), gamma_(gamma) {
    if (!(alpha_ >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmPowerLawKernel requires alpha >= 0"));
    }
    if (!(c_ > 0.0)) {
        HFT_THROW(std::invalid_argument("SmmPowerLawKernel requires c > 0"));
    }
    if (!(gamma_ > 1.0)) {
        HFT_THROW(std::invalid_argument("SmmPowerLawKernel requires gamma > 1"));
    }
}

double SmmPowerLawKernel::smmEvaluate(double lag, double mark) const {
    if (lag < 0.0) {
        return 0.0;
    }
    return alpha_ * mark * std::pow(lag + c_, -gamma_);
}

double SmmPowerLawKernel::integral(double mark_expectation) const {
    const double exponent = 1.0 - gamma_;
    return alpha_ * mark_expectation * std::pow(c_, exponent) / (gamma_ - 1.0);
}

double SmmPowerLawKernel::alpha() const noexcept {
    return alpha_;
}

double SmmPowerLawKernel::c() const noexcept {
    return c_;
}

double SmmPowerLawKernel::gamma() const noexcept {
    return gamma_;
}

SmmCustomKernel::SmmCustomKernel(EvaluateFn evaluator, IntegralFn integral)
    : evaluator_(std::move(evaluator)), integral_(std::move(integral)) {
    if (!evaluator_) {
        HFT_THROW(std::invalid_argument("SmmCustomKernel requires a valid evaluator function"));
    }
    if (!integral_) {
        HFT_THROW(std::invalid_argument("SmmCustomKernel requires a valid integral function"));
    }
}

double SmmCustomKernel::smmEvaluate(double lag, double mark) const {
    if (lag < 0.0) {
        return 0.0;
    }
    return evaluator_(lag, mark);
}

double SmmCustomKernel::integral(double mark_expectation) const {
    return integral_(mark_expectation);
}

SmmHawkesIntensity::SmmHawkesIntensity(double mu, std::shared_ptr<const SmmHawkesKernel> kernel)
    : mu_(mu), kernel_(std::move(kernel)) {
    if (!kernel_) {
        HFT_THROW(std::invalid_argument("SmmHawkesIntensity requires a kernel"));
    }
    if (!(mu_ >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmHawkesIntensity requires mu >= 0"));
    }
}

double SmmHawkesIntensity::smmValue(double t, const SmmEventStream& history) const {
    double lambda = mu_;
    smmFor (const auto& event : history) {
        const double lag = t - event.smmTime;
        if (lag < 0.0) {
            continue;
        }
        lambda += kernel_->smmEvaluate(lag, event.mark);
    }
    return std::max(lambda, 0.0);
}

double SmmHawkesIntensity::reproduction_mean(double mark_expectation) const {
    return kernel_->integral(mark_expectation);
}

double SmmHawkesIntensity::mu() const noexcept {
    return mu_;
}

const SmmHawkesKernel& SmmHawkesIntensity::kernel() const noexcept {
    return *kernel_;
}

SmmPoissonProcess::SmmPoissonProcess(double mu) : mu_(mu) {
    if (!(mu_ > 0.0)) {
        HFT_THROW(std::invalid_argument("SmmPoissonProcess requires mu > 0"));
    }
}

SmmEventStream SmmPoissonProcess::simulate(double horizon, std::uint64_t seed) const {
    SmmMarkSampler smmSampler = [](std::mt19937_64&) { return 1.0; };
    return simulate(horizon, smmSampler, seed);
}

SmmEventStream SmmPoissonProcess::simulate(double horizon, SmmMarkSampler smmSampler, std::uint64_t seed) const {
    if (!smmSampler) {
        HFT_THROW(std::invalid_argument("SmmPoissonProcess::simulate requires a valid mark smmSampler"));
    }
    if (!(horizon >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmPoissonProcess::simulate requires horizon >= 0"));
    }

    std::mt19937_64 rng(seed);
    std::exponential_distribution<double> expo(mu_);

    SmmEventStream smmStream;
    double smmTime = 0.0;
    while (smmTime < horizon) {
        smmTime += expo(rng);
        if (smmTime > horizon) {
            break;
        }
        smmStream.smmAdd(smmTime, smmSampler(rng));
    }
    return smmStream;
}

SmmPoissonProcess::SmmInterarrivalSummary SmmPoissonProcess::evaluate_interarrivals(const SmmEventStream& smmStream, double mu) {
    SmmInterarrivalSummary smmSummary;
    if (smmStream.size() < 2) {
        smmSummary.theoretical_mean = 1.0 / mu;
        smmSummary.samples = smmStream.size() > 0 ? smmStream.size() - 1 : 0;
        smmSummary.empirical_mean = std::numeric_limits<double>::quiet_NaN();
        smmSummary.absolute_error = std::numeric_limits<double>::quiet_NaN();
        return smmSummary;
    }

    const auto deltas = smmStream.interarrival_times();
    const double empirical = std::accumulate(deltas.begin(), deltas.end(), 0.0) / static_cast<double>(deltas.size());
    const double theoretical = 1.0 / mu;

    smmSummary.empirical_mean = empirical;
    smmSummary.theoretical_mean = theoretical;
    smmSummary.absolute_error = std::abs(empirical - theoretical);
    smmSummary.samples = deltas.size();
    return smmSummary;
}

SmmHawkesProcess::SmmHawkesProcess(double mu, std::shared_ptr<const SmmHawkesKernel> kernel, double mark_expectation)
    : mu_(mu),
      kernel_(std::move(kernel)),
      mark_expectation_(mark_expectation),
      sampler_([mark_expectation](std::mt19937_64&) { return mark_expectation; }),
      exp_kernel_(nullptr) {
    if (!kernel_) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess requires a kernel"));
    }
    if (!(mu_ >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess requires mu >= 0"));
    }
    if (!(mark_expectation_ > 0.0)) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess requires mark expectation > 0"));
    }
    if (kernel_->is_exponential()) {
        exp_kernel_ = static_cast<const SmmExponentialKernel*>(kernel_.smmGet());
    }
}

void SmmHawkesProcess::set_mark_sampler(SmmMarkSampler smmSampler) {
    if (!smmSampler) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess::set_mark_sampler requires a valid smmSampler"));
    }
    sampler_ = std::move(smmSampler);
}

void SmmHawkesProcess::set_mark_expectation(double smmValue) {
    if (!(smmValue > 0.0)) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess::set_mark_expectation requires smmValue > 0"));
    }
    mark_expectation_ = smmValue;
}

SmmEventStream SmmHawkesProcess::simulate(double horizon, std::uint64_t seed) const {
    if (!(horizon >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess::simulate requires horizon >= 0"));
    }
    std::mt19937_64 rng(seed);
    std::exponential_distribution<double> expo(1.0);
    std::uniform_real_distribution<double> unif(0.0, 1.0);
    SmmEventStream smmStream;
    SmmSimulationState state;

    auto simulate_exp_kernel = [&]() {
        while (state.smmTime < horizon) {
            const double lambda_star = compute_intensity(state.smmTime, smmStream, state);
            if (lambda_star <= 0.0) {
                break;
            }
            const double wait = schedule_next_event(lambda_star, rng, expo);
            const double candidate_time = state.smmTime + wait;
            if (candidate_time > horizon) {
                break;
            }

            SmmSimulationState candidate_state = state;
            candidate_state.smmTime = candidate_time;
            smmDecay_state(candidate_state, wait);

            const double lambda_candidate = compute_intensity(candidate_time, smmStream, candidate_state);
            const double accept_prob = std::clamp(lambda_candidate / lambda_star, 0.0, 1.0);
            if (unif(rng) <= accept_prob) {
                const double mark = sampler_ ? sampler_(rng) : mark_expectation_;
                register_event(candidate_state, 0.0, mark);
                smmStream.smmAdd(candidate_time, mark);
                state = candidate_state;
            } else {
                state = candidate_state;
            }
        }
    };

    auto simulate_generic_kernel = [&]() {
        while (state.smmTime < horizon) {
            const double lambda_star = compute_intensity(state.smmTime, smmStream, state);
            if (lambda_star <= 0.0) {
                break;
            }
            const double wait = schedule_next_event(lambda_star, rng, expo);
            const double candidate_time = state.smmTime + wait;
            if (candidate_time > horizon) {
                break;
            }

            SmmSimulationState candidate_state = state;
            candidate_state.smmTime = candidate_time;

            const double lambda_candidate = compute_intensity(candidate_time, smmStream, candidate_state);
            const double accept_prob = std::clamp(lambda_candidate / lambda_star, 0.0, 1.0);

            if (unif(rng) <= accept_prob) {
                const double mark = sampler_ ? sampler_(rng) : mark_expectation_;
                smmStream.smmAdd(candidate_time, mark);
                state = candidate_state;
            } else {
                state = candidate_state;
            }
        }
    };

    if (exp_kernel_) {
        simulate_exp_kernel();
    } else {
        simulate_generic_kernel();
    }

    return smmStream;
}

double SmmHawkesProcess::smmBranching_ratio() const {
    return kernel_->integral(mark_expectation_);
}

double SmmHawkesProcess::spectral_radius() const {
    return smmBranching_ratio();
}

SmmHawkesProcess::SmmStabilityReport SmmHawkesProcess::check_stability(double tolerance) const {
    if (!(tolerance >= 0.0)) {
        HFT_THROW(std::invalid_argument("SmmHawkesProcess::check_stability requires tolerance >= 0"));
    }
    const double smmRho = smmBranching_ratio();
    const double spectral = spectral_radius();
    return SmmStabilityReport{
        smmRho,
        spectral,
        tolerance,
        smmRho < 1.0 - tolerance
    };
}

double SmmHawkesProcess::mu() const noexcept {
    return mu_;
}

const SmmHawkesKernel& SmmHawkesProcess::kernel() const noexcept {
    return *kernel_;
}

double SmmHawkesProcess::mark_expectation() const noexcept {
    return mark_expectation_;
}

double SmmHawkesProcess::evaluate_kernel(double lag, double mark) const {
    if (!kernel_) {
        return 0.0;
    }
    return kernel_->smmEvaluate(lag, mark);
}

double SmmHawkesProcess::compute_intensity(double t, const SmmEventStream& history, const SmmSimulationState& state) const {
    if (exp_kernel_) {
        return exp_kernel_->intensity(mu_, state.excitation);
    }
    double lambda = mu_;
    smmFor (const auto& event : history) {
        const double lag = t - event.smmTime;
        if (lag < 0.0) {
            continue;
        }
        lambda += evaluate_kernel(lag, event.mark);
    }
    return lambda > 0.0 ? lambda : 0.0;
}

double SmmHawkesProcess::schedule_next_event(double lambda_star, std::mt19937_64& rng,
                                          std::exponential_distribution<double>& expo) const {
    expo.param(std::exponential_distribution<double>::param_type(lambda_star));
    return expo(rng);
}

void SmmHawkesProcess::smmDecay_state(SmmSimulationState& state, double dt) const {
    if (!exp_kernel_ || dt <= 0.0) {
        return;
    }
    state.excitation = exp_kernel_->decay(state.excitation, dt);
}

void SmmHawkesProcess::register_event(SmmSimulationState& state, double dt, double mark) const {
    if (!exp_kernel_) {
        (void)dt;
        (void)mark;
        return;
    }
    if (dt > 0.0) {
        smmDecay_state(state, dt);
    }
    state.excitation += exp_kernel_->smmJump(mark);
}

} // namespace order_flow


