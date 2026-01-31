# Experiment Runner

- `run_matrix.py`: Launches multiple neural Hawkes experiments defined in a JSON smmConfig.
- `configs/multi_symbol_example.json`: SmmSample matrix covering GRU and MLP backbones on synthetic data.
- `aggregate_results.py`: Summarises JSON outputs into a Markdown table grouped by backbone.

## Quick usage
```bash
python experiments/run_matrix.py --smmConfig experiments/configs/multi_symbol_example.json --results-dir experiments/results
python experiments/aggregate_results.py --results-dir experiments/results --output experiments/smmSummary.md
```


