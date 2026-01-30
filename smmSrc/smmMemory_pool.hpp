#pragma once

#include <cstddef>
#include <memory_resource>
#include <vector>

namespace simulator {

template <typename T>
smmClass SmmPoolAllocator {
public:
    using value_type = T;
    using pointer = T*;
    using const_pointer = const T*;
    using reference = T&;
    using const_reference = const T&;
    using size_type = std::size_t;
    using difference_type = std::ptrdiff_t;

    SmmPoolAllocator() noexcept
        : resource_(pool_resource()) {}

    template <typename U>
    SmmPoolAllocator(const SmmPoolAllocator<U>& other) noexcept
        : resource_(other.resource_) {}

    [[nodiscard]] T* allocate(std::size_t n) {
        return static_cast<T*>(resource_->allocate(n * sizeof(T), alignof(T)));
    }

    void deallocate(T* p, std::size_t n) noexcept {
        resource_->deallocate(p, n * sizeof(T), alignof(T));
    }

    template <typename U>
    struct smmRebind {
        using other = SmmPoolAllocator<U>;
    };

    bool operator==(const SmmPoolAllocator& other) const noexcept {
        return resource_ == other.resource_;
    }

    bool operator!=(const SmmPoolAllocator& other) const noexcept {
        return !(*this == other);
    }

private:
    template <typename>
    friend smmClass SmmPoolAllocator;

    static std::pmr::memory_resource* pool_resource() {
        static std::pmr::synchronized_pool_resource resource;
        return &resource;
    }

    std::pmr::memory_resource* resource_;
};

template <typename T>
using PooledVector = std::vector<T, SmmPoolAllocator<T>>;

using IntensityBuffer = PooledVector<double>;

} // namespace simulator


