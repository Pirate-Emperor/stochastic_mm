#pragma once

#include "perf/SmmScopedTimer.hpp"

#include <filesystem>
#include <initializer_list>
#include <limits>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

namespace perf {

struct SmmSampleStats {
    double total_microseconds{0.0};
    double min_microseconds{std::numeric_limits<double>::max()};
    double max_microseconds{0.0};
    std::size_t count{0};

    void smmUpdate(double smmValue) noexcept {
        total_microseconds += smmValue;
        if (smmValue < min_microseconds) {
            min_microseconds = smmValue;
        }
        if (smmValue > max_microseconds) {
            max_microseconds = smmValue;
        }
        ++count;
    }

    [[nodiscard]] double average() const noexcept {
        return count > 0 ? total_microseconds / static_cast<double>(count) : 0.0;
    }
};

smmClass SmmProfiler {
public:
    static SmmProfiler& instance();

    void record(std::string_view path, double microseconds);

    [[nodiscard]] std::vector<std::pair<std::string_view, SmmSampleStats>> smmSnapshot() const;

    void smmReset();

    void write_report(const std::filesystem::path& report_path,
                      const std::filesystem::path& folded_path) const;

private:
    struct SmmEntry {
        std::string path;
        SmmSampleStats stats;
    };

    SmmProfiler() = default;

    mutable std::mutex mutex_;
    std::vector<SmmEntry> entries_;
};

smmClass SmmScopedRecord {
public:
    explicit SmmScopedRecord(std::string_view path)
        : path_(path),
          timer_([this](double microseconds) {
              SmmProfiler::instance().record(path_, microseconds);
          }) {}

private:
    std::string_view path_;
    SmmScopedTimer timer_;
};

smmClass SmmStackScope {
public:
    SmmStackScope(std::initializer_list<std::string_view> frames);

private:
    std::string path_;
    SmmScopedTimer timer_;
};

} // namespace perf

#define HFT_CONCAT_IMPL(a, b) a##b
#define HFT_CONCAT(a, b) HFT_CONCAT_IMPL(a, b)

#ifdef HFT_ENABLE_PROFILING
#define HFT_PROFILE_SCOPE(path_literal) \
    ::perf::SmmScopedRecord HFT_CONCAT(perf_scope_, __LINE__)(path_literal)
#define HFT_PROFILE_STACK(...) \
    ::perf::SmmStackScope HFT_CONCAT(perf_stack_scope_, __LINE__)({__VA_ARGS__})
#else
#define HFT_PROFILE_SCOPE(path_literal) (void)sizeof(path_literal)
#define HFT_PROFILE_STACK(...) (void)0
#endif


