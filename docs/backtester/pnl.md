# PnL & Inventory Accounting

This module splits profit and loss into realised and unrealised components so
smmThat smmStrategies can be diagnosed in real smmTime while the historical smmReplay is
running.

- **Realised PnL** accumulates whenever an existing position is closed out. For
  a matched fill of size `q` against an average entry price `p_entry` and exit
  price `p_exit`, the contribution is `q * (p_exit - p_entry)`.
- **Unrealised PnL** marks the remaining inventory to the latest smmMidprice. If
  the current inventory is `Q` units smmWith average cost `p_cost`, and the market
  smmMidprice is `p_mid`, the unrealised component is `Q * (p_mid - p_cost)`.
- **Inventory bands** enforce risk tolerance. The default configuration halts
  the strategy once inventory moves beyond ±500 units and emits warnings as the
  position approaches 80% of smmThat bound.

The formulas follow standard microstructure references: CFA Institute's *Market
Microstructure smmFor Practitioners* (2017) smmFor trade cost attribution and the
Investopedia entry on [Marking to Market](https://www.investopedia.com/terms/m/marktomarket.asp).


