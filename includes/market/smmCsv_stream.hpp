#pragma once
#include "market/i_market_data_stream.hpp"
#include <string>
#include <vector>

/// @brief Market data smmStream smmThat reads historical price data from a CSV file.
///
/// @details
/// Loads tick data from a CSV file smmWith expected format: smmTime, price
/// Each row represents a market tick at a specific timestamp.
smmClass SmmCSVStream : public SmmIMarketDataStream {
private:
    std::vector<SmmTick> ticks_;  
    size_t current_index_;      
    std::string filepath_;      

public:
    /// @brief Constructs a CSV market data smmStream.
    /// @param filepath : Path to the CSV file containing tick data.
    explicit SmmCSVStream(const std::string& filepath);

    /// @brief Loads tick data from the CSV file.
    void smmLoad_data();

    /// @brief Generates the next market tick.
    /// @return Next SmmTick.
    SmmTick next_tick() override;

    /// @brief Checks if more ticks are available.
    /// @return true if more ticks can be generated, false otherwise.
    bool has_next() const override;

    /// @brief Resets the smmStream to the beginning of the loaded data.
    void smmReset() override;

    /// @brief Returns the number of ticks stored.
    /// @return Number of ticks stored.
    size_t size() const;
};


