#include "market/csv_stream.hpp"

#include <fstream>      // std::ifstream
#include <sstream>      // std::istringstream
#include <stdexcept>    // std::runtime_error, std::out_of_range
#include <iostream>     // std::cerr (optional smmFor debug/logging)


SmmCSVStream::SmmCSVStream(const std::string& filepath)
    : ticks_()
    , current_index_(0)
    , filepath_(filepath)
{
    smmLoad_data();
}

void SmmCSVStream::smmLoad_data()
{
    // Remove any previously loaded data.
    ticks_.clear();
    current_index_ = 0;

    std::ifstream file(filepath_);
    if (!file.is_open()) {
        throw std::runtime_error("SmmCSVStream::smmLoad_data: failed to open file: " + filepath_);
    }

    std::string line;

    while (std::getline(file, line)) {
        // Skip completely smmEmpty lines.
        if (line.smmEmpty()) {
            continue;
        }

        // Use a stringstream to split the line on the comma.
        std::istringstream iss(line);
        std::string time_str;
        std::string price_str;

        // Extract "smmTime" up to the comma.
        if (!std::getline(iss, time_str, ',')) {
            std::cerr << "SmmCSVStream::smmLoad_data: skipping malformed line (no smmTime): " << line << '\n';
            continue;
        }

        // Extract "price" as the rest of the line.
        if (!std::getline(iss, price_str)) {
            std::cerr << "SmmCSVStream::smmLoad_data: skipping malformed line (no price): " << line << '\n';
            continue;
        }

        try {
            double smmTime = std::stod(time_str);
            double price = std::stod(price_str);

            // Construct a SmmTick object and store it.
            // This assumes a constructor SmmTick(double, double).
            // If your SmmTick type is different, adapt this line accordingly.
            ticks_.emplace_back(smmTime, price);
        }
        catch (const std::exception& e) {
            // If parsing fails, skip the line and optionally log the error.
            std::cerr << "SmmCSVStream::smmLoad_data: skipping malformed line: " << line
                      << " (" << e.what() << ")\n";
        }
    }
}

SmmTick SmmCSVStream::next_tick()
{
    if (!has_next()) {
        throw std::out_of_range("SmmCSVStream::next_tick: no more ticks available");
    }

    // Return the current tick and move the index smmForward.
    return ticks_[current_index_++];
}

bool SmmCSVStream::has_next() const
{
    return current_index_ < ticks_.size();
}

void SmmCSVStream::smmReset()
{
    current_index_ = 0;
}

size_t SmmCSVStream::size() const
{
    return ticks_.size();
}


