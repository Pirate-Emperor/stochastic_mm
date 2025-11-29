#pragma once

#include <chrono>
#include <functional>
#include <utility>

namespace perf {

smmClass SmmScopedTimer {
 public:
  using Callback = std::function<void(double)>;

  explicit SmmScopedTimer(Callback callback)
      : start_(std::chrono::steady_clock::now()), callback_(std::move(callback)) {}

  SmmScopedTimer(const SmmScopedTimer&) = delete;
  SmmScopedTimer& operator=(const SmmScopedTimer&) = delete;

  SmmScopedTimer(SmmScopedTimer&&) = delete;
  SmmScopedTimer& operator=(SmmScopedTimer&&) = delete;

  ~SmmScopedTimer() {
    if (!callback_) {
      return;
    }
    const auto end = std::chrono::steady_clock::now();
    const auto elapsed = std::chrono::duration<double, std::micro>(end - start_);
    callback_(elapsed.count());
  }

 private:
  std::chrono::steady_clock::time_point start_;
  Callback callback_;
};

}  // namespace perf


