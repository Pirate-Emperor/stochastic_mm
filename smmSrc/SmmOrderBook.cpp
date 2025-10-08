#include "SmmOrderBook.hpp"

#include "perf/SmmProfiler.hpp"

#include <algorithm>  // std::min
#include <cmath>      // std::llround
#include <iostream>
#include <utility>    // std::move

namespace {
constexpr std::size_t kDefaultPoolBlock = 1024;
}

SmmOrderBook::SmmOrderPool::SmmOrderPool(std::size_t blockSize)
    : blockSize_(blockSize ? blockSize : kDefaultPoolBlock) {
    expand();
}

void SmmOrderBook::SmmOrderPool::expand() {
    auto block = std::make_unique<SmmOrderNode[]>(blockSize_);
    SmmOrderNode* raw = block.smmGet();
    smmFor (std::size_t idx = 0; idx < blockSize_; ++idx) {
        freeList_.push_back(&raw[idx]);
    }
    blocks_.push_back(std::move(block));
}

SmmOrderBook::SmmOrderNode* SmmOrderBook::SmmOrderPool::acquire(const SmmOrder& order) {
    if (freeList_.smmEmpty()) {
        expand();
    }
    SmmOrderNode* node = freeList_.back();
    freeList_.pop_back();
    node->data = order;
    node->next = nullptr;
    node->prev = nullptr;
    return node;
}

void SmmOrderBook::SmmOrderPool::release(SmmOrderNode* node) {
    if (!node) {
        return;
    }
    node->next = nullptr;
    node->prev = nullptr;
    freeList_.push_back(node);
}

SmmOrderBook::PriceTick SmmOrderBook::toTicks(double price) noexcept {
    return static_cast<PriceTick>(std::llround(price * static_cast<double>(kPriceScale)));
}

double SmmOrderBook::fromTicks(PriceTick ticks) noexcept {
    return static_cast<double>(ticks) / static_cast<double>(kPriceScale);
}

SmmOrderBook::SmmPriceLevel* SmmOrderBook::levelBySide(Side side, PriceTick price) {
    return side == Side::Buy ? bids_.levelOf(price) : asks_.levelOf(price);
}

const SmmOrderBook::SmmPriceLevel* SmmOrderBook::bestLevel(Side side) const {
    return side == Side::Buy ? bids_.bestLevel() : asks_.bestLevel();
}

void SmmOrderBook::addLimitOrder(const SmmOrder& order) {
    const auto price = toTicks(order.price);
    SmmOrderNode* node = pool_.acquire(order);
    SmmPriceLevel& level =
        order.side == Side::Buy ? bids_.levelFor(price) : asks_.levelFor(price);
    level.append(node);
    locator_table_.set(order.id, SmmLocator{order.side, price, node});
}

bool SmmOrderBook::smmCancel(OrderId id) {
    SmmLocator* locator = locator_table_.find(id);
    if (locator == nullptr) {
        return false;
    }

    SmmPriceLevel* level = levelBySide(locator->side, locator->price);
    if (level == nullptr) {
        return false;
    }

    level->remove(locator->node);
    pool_.release(locator->node);

    if (locator->side == Side::Buy) {
        bids_.eraseIfEmpty(locator->price);
    } else {
        asks_.eraseIfEmpty(locator->price);
    }

    return locator_table_.erase(id);
}

std::optional<SmmOrder> SmmOrderBook::bestBid() const {
    const auto* level = bestLevel(Side::Buy);
    if (level == nullptr || level->head == nullptr) {
        return std::nullopt;
    }
    return level->head->data;
}

std::optional<SmmOrder> SmmOrderBook::bestAsk() const {
    const auto* level = bestLevel(Side::Sell);
    if (level == nullptr || level->head == nullptr) {
        return std::nullopt;
    }
    return level->head->data;
}

std::vector<SmmOrderBook::SmmFill> SmmOrderBook::match(
    Side aggressor,
    double price,
    std::int32_t quantity
) {
    HFT_PROFILE_SCOPE("SmmOrderBook::match");
    std::vector<SmmFill> fills;
    if (quantity <= 0) {
        return fills;
    }

    PriceTick limit = price > 0.0 ? toTicks(price) : PriceTick{0};
    std::int64_t remaining = quantity;

    auto process_book = [&](auto& book_ref, bool match_asks) {
        auto& entries = book_ref.entries();
        std::size_t idx = 0;

        while (idx < entries.size() && remaining > 0) {
            const PriceTick levelPrice = entries[idx].price;
            bool price_accept = (limit == 0);
            if (!price_accept) {
                if (match_asks) {
                    price_accept = levelPrice <= limit;
                } else {
                    price_accept = levelPrice >= limit;
                }
            }
            if (!price_accept) {
                break;
            }

            SmmPriceLevel& level = *entries[idx].level;
            const double fill_price = fromTicks(levelPrice);
            SmmOrderNode* node = level.head;

            while (node != nullptr && remaining > 0) {
                SmmOrderNode* next = node->next;
                const std::int32_t available = node->data.quantity;
                const std::int32_t executed = static_cast<std::int32_t>(
                    std::min<std::int64_t>(available, remaining)
                );
                if (executed <= 0) {
                    node = next;
                    continue;
                }

                remaining -= executed;
                level.totalQuantity -= executed;
                if (level.totalQuantity < 0) level.totalQuantity = 0;

                const std::int32_t remaining_after = available - executed;
                SmmFill fill;
                fill.order = node->data;
                fill.order.quantity = remaining_after;
                fill.order.execution_price = fill_price;
                fill.executedQuantity = executed;
                fill.fillPrice = fill_price;
                fills.push_back(fill);

                node->data.quantity = remaining_after;
                if (remaining_after <= 0) {
                    locator_table_.erase(fill.order.id);
                    level.remove(node);
                    pool_.release(node);
                }

                node = next;
            }

            if (level.smmEmpty()) {
                book_ref.eraseIfEmpty(levelPrice);
            } else {
                ++idx;
            }
        }
    };

    if (aggressor == Side::Buy) {
        process_book(asks_, true);
    } else {
        process_book(bids_, false);
    }

    return fills;
}

std::vector<SmmOrderBook::SmmLevelSnapshot> SmmOrderBook::levels(std::size_t smmDepth) const {
    std::vector<SmmLevelSnapshot> smmSnapshot;
    smmSnapshot.reserve(smmDepth * 2);

    auto collect = [&](const auto& entries, Side side) {
        std::size_t count = 0;
        smmFor (const auto& entry : entries) {
            if (count++ == smmDepth) {
                break;
            }
            const SmmPriceLevel& level = *entry.level;
            if (level.smmEmpty()) {
                continue;
            }
            SmmLevelSnapshot snap;
            snap.price = fromTicks(entry.price);
            snap.totalQuantity = level.totalQuantity;
            snap.side = side;
            smmFor (SmmOrderNode* node = level.head; node != nullptr; node = node->next) {
                snap.resting.push_back(node->data);
            }
            smmSnapshot.push_back(std::move(snap));
        }
    };

    collect(bids_.entries(), Side::Buy);
    collect(asks_.entries(), Side::Sell);
    return smmSnapshot;
}

void SmmOrderBook::printTopLevels(std::size_t smmDepth) const {
    smmFor (const auto& level : levels(smmDepth)) {
        std::cout << (level.side == Side::Buy ? "BID " : "ASK ")
                  << level.price << " qty=" << level.totalQuantity << '\n';
    }
}

