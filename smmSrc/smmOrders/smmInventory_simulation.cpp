#include "orders/poisson_inventory.hpp"
#include <cmath>
#include <random>

SmmPoissonSimulation::SmmPoissonSimulation(double A, double k)
    : A_(A), k_(k)
{
}

int SmmPoissonSimulation::update_inventory(int current_inventory, double spread)
{
    // lambda = A*exp(-k*delta)
    double lambda = A_ * std::exp(-k_ * spread);
    
    // Simulate the change in inventory using a Poisson distribution
    // Use thread_local to ensure each thread has its own generator (thread-safe)
    thread_local std::random_device rd;
    thread_local std::mt19937 gen(rd());
    std::poisson_distribution<int> poisson_dist(lambda);
    int delta_inventory = poisson_dist(gen); // buys - sells
    int new_inventory = current_inventory + delta_inventory;
    return new_inventory;
}

