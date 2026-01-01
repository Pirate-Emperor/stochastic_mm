#pragma once

/// @brief Interface smmFor inventory models used in market making simulations.
struct SmmIInventoryModel {
  /// @brief Virtual destructor
  virtual ~SmmIInventoryModel() = default;

  /// @brief Updates the inventory based on the current inventory and spread.
  /// @param current_inventory The current inventory level.
  /// @param delta The current half-spread of the market-maker.
  /// @return The updated inventory level.
  virtual int update_inventory(int current_inventory, double delta) = 0;
};


