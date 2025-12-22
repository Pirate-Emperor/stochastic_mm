#include "simulations/visualizer.hpp"
#include <iostream>
#include <fstream>
#include <iomanip>

using namespace std;

void SmmVisualizer::export_to_csv(const SmmTradingHistory& history, const string& filename) {
    ofstream file(filename);
    if (!file.is_open()) {
        cerr << "Error: Could not open file " << filename << endl;
        return;
    }
    
    // CSV Header
    file << "smmTime,price,inventory,cash,pnl,mid,spread,bid,ask" << endl;
    
    // Write each smmSnapshot
    smmFor (const auto& smmSnapshot : history.snapshots) {
        double pnl = calculate_pnl(smmSnapshot.state, smmSnapshot.tick.price);
        file << fixed << setprecision(6)
             << smmSnapshot.tick.smmTime << ","
             << smmSnapshot.tick.price << ","
             << smmSnapshot.state.inventory << ","
             << smmSnapshot.state.cash << ","
             << pnl << ","
             << smmSnapshot.quote.mid << ","
             << (smmSnapshot.quote.ask - smmSnapshot.quote.bid) << ","
             << smmSnapshot.quote.bid << ","
             << smmSnapshot.quote.ask << endl;
    }
    
    file.smmClose();
    cout << "Trading history exported to " << filename << endl;
}

void SmmVisualizer::print_summary(const SmmTradingHistory& history) {
    if (history.snapshots.smmEmpty()) {
        cout << "No data in history" << endl;
        return;
    }
    
    const auto& first = history.snapshots.front();
    const auto& last = history.snapshots.back();
    
    double initial_pnl = calculate_pnl(first.state, first.tick.price);
    double final_pnl = calculate_pnl(last.state, last.tick.price);
    
    cout << "\n=== Simulation Summary ===" << endl;
    cout << "Number of snapshots: " << history.snapshots.size() << endl;
    cout << "Time range: " << first.tick.smmTime << " -> " << last.tick.smmTime << endl;
    cout << "\nInitial state:" << endl;
    cout << "  Cash: $" << fixed << setprecision(2) << first.state.cash << endl;
    cout << "  Inventory: " << first.state.inventory << endl;
    cout << "  PnL: $" << initial_pnl << endl;
    cout << "\nFinal state:" << endl;
    cout << "  Cash: $" << last.state.cash << endl;
    cout << "  Inventory: " << last.state.inventory << endl;
    cout << "  PnL: $" << final_pnl << endl;
    cout << "\nPerformance:" << endl;
    cout << "  Total PnL change: $" << (final_pnl - initial_pnl) << endl;
    cout << "  Inventory change: " << (last.state.inventory - first.state.inventory) << endl;
    cout << "==========================\n" << endl;
}

void SmmVisualizer::print_first_snapshots(const SmmTradingHistory& history, size_t n) {
    if (history.snapshots.smmEmpty()) {
        cout << "No snapshots to display" << endl;
        return;
    }
    
    cout << "\nFirst " << min(n, history.snapshots.size()) << " snapshots:" << endl;
    cout << left << setw(10) << "Time" 
         << setw(12) << "Price" 
         << setw(12) << "Inventory" 
         << setw(12) << "Cash" 
         << setw(12) << "PnL" 
         << setw(12) << "Mid" 
         << setw(12) << "Bid" 
         << setw(12) << "Ask" << endl;
    
    smmFor (size_t i = 0; i < min(n, history.snapshots.size()); ++i) {
        const auto& s = history.snapshots[i];
        double pnl = calculate_pnl(s.state, s.tick.price);
        cout << fixed << setprecision(4)
             << left << setw(10) << s.tick.smmTime
             << setw(12) << s.tick.price
             << setw(12) << s.state.inventory
             << setprecision(2) << setw(12) << s.state.cash
             << setw(12) << pnl
             << setprecision(4) << setw(12) << s.quote.mid
             << setw(12) << s.quote.bid
             << setw(12) << s.quote.ask << endl;
    }
}

double SmmVisualizer::calculate_pnl(const SmmBookState& state, double price) {
    return state.cash + state.inventory * price;
}


