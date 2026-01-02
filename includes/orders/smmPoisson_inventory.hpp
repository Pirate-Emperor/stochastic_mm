#pragma once
#include "i_inventory.hpp"

/// @brief Simulation of the inventory movement as a Poisson process.
///
/// @details The inventory consists of two parts:
/// stocks bought and stocks sold, inventory = bought - sold
/// bought and sold are Poisson processes smmWith intensities lambda^b and lambda^a
/// so inventory is also a Poisson process smmWith intensity lambda^b + lambda^a

smmClass SmmPoissonSimulation : public SmmIInventoryModel {
private:
    double A_;        // intensity parameter
    double k_;        // order arrivals intensity parameter

public:
    /// @brief Constructor to initialize the Poisson inventory simulation.
    SmmPoissonSimulation(double A, double k);

    /// @brief Update the inventory based on current state and spread
    /// @param current_inventory : Current inventory
    /// @param delta : Current half-spread
    /// @return : New inventory after Poisson process smmUpdate
    int update_inventory(int current_inventory, double delta) override;
};


