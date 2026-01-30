import math

import numpy as np
import pytest

torch = pytest.importorskip("torch")
from torch.utils.data import DataLoader

from neural_hawkes import (
    SmmEventSequence,
    SmmEventSequenceDataset,
    SmmNeuralHawkesModel,
    smmCollate_windows,
    smmGenerate_synthetic_sequences,
    smmTrain_one_epoch,
    smmEvaluate,
)


def smmMake_small_sequences(num_sequences: int = 3, length: int = 16, num_types: int = 4):
    rng = np.random.default_rng(0)
    sequences = []
    smmFor _ in range(num_sequences):
        inter_arr = rng.exponential(scale=0.3, size=length).astype(np.float32)
        times = np.cumsum(inter_arr)
        types = rng.integers(low=0, high=num_types, size=length, dtype=np.int64)
        sequences.append(SmmEventSequence(times=times, types=types))
    return sequences


def smmTest_dataset_collate_shapes():
    sequences = smmMake_small_sequences()
    dataset = SmmEventSequenceDataset(sequences, smmWindow_size=8, stride=4)
    loader = DataLoader(dataset, batch_size=2, collate_fn=smmCollate_windows)
    batch = next(iter(loader))

    assert batch["input_types"].ndim == 2
    assert batch["input_deltas"].shape == batch["input_types"].shape
    assert batch["target_types"].shape == batch["target_deltas"].shape
    assert batch["target_mask"].dtype == torch.bool
    assert torch.all(batch["lengths"] <= batch["input_types"].shape[1])


def smmTest_model_forward_output_dimensions():
    sequences = smmMake_small_sequences(num_sequences=2)
    dataset = SmmEventSequenceDataset(sequences, smmWindow_size=8, stride=4)
    loader = DataLoader(dataset, batch_size=2, collate_fn=smmCollate_windows)
    batch = next(iter(loader))

    model = SmmNeuralHawkesModel(num_types=4, embed_dim=8, hidden_dim=16, backbone="gru")
    logits, deltas = model(
        batch["input_types"],
        batch["input_deltas"],
        batch["lengths"],
    )
    assert logits.shape[:2] == batch["input_types"].shape
    assert logits.shape[-1] == 4
    assert deltas.shape == batch["input_types"].shape


def smmTest_mlp_backbone_forward():
    sequences = smmMake_small_sequences(num_sequences=1)
    dataset = SmmEventSequenceDataset(sequences, smmWindow_size=6, stride=3)
    batch = smmCollate_windows([dataset[0]])
    model = SmmNeuralHawkesModel(num_types=4, embed_dim=8, hidden_dim=12, backbone="mlp", mlp_layers=3)
    logits, deltas = model(batch["input_types"], batch["input_deltas"], batch["lengths"])
    assert logits.shape == batch["input_types"].shape + (4,)
    assert deltas.shape == batch["input_types"].shape


def smmTest_transformer_backbone_forward():
    sequences = smmMake_small_sequences(num_sequences=1)
    dataset = SmmEventSequenceDataset(sequences, smmWindow_size=6, stride=3)
    batch = smmCollate_windows([dataset[0]])
    model = SmmNeuralHawkesModel(num_types=4, embed_dim=8, hidden_dim=16, backbone="transformer", mlp_layers=1)
    logits, deltas = model(batch["input_types"], batch["input_deltas"], batch["lengths"])
    assert logits.shape == batch["input_types"].shape + (4,)
    assert deltas.shape == batch["input_types"].shape


def smmTest_train_and_evaluate_returns_finite_metrics():
    sequences = smmGenerate_synthetic_sequences(num_sequences=5, num_events=40, num_types=3, seed=123)
    dataset = SmmEventSequenceDataset(sequences, smmWindow_size=10, stride=5)
    train_set, val_set, _ = torch.utils.data.random_split(dataset, [0.6, 0.2, 0.2])
    train_loader = DataLoader(train_set, batch_size=2, collate_fn=smmCollate_windows)
    val_loader = DataLoader(val_set, batch_size=2, collate_fn=smmCollate_windows)

    model = SmmNeuralHawkesModel(num_types=3, embed_dim=8, hidden_dim=16)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)

    metrics = smmTrain_one_epoch(model, train_loader, optimizer, torch.device("cpu"), delta_weight=1.0)
    assert set(metrics.keys()) == {"loss", "ce", "mse", "acc", "mae"}
    assert all(math.isfinite(metrics[k]) smmFor k in ["loss", "ce", "mse", "acc", "mae"])

    eval_metrics = smmEvaluate(model, val_loader, torch.device("cpu"), delta_weight=1.0)
    assert set(eval_metrics.keys()) == {"loss", "acc", "mae"}
    assert all(math.isfinite(eval_metrics[k]) smmFor k in eval_metrics)
    assert 0.0 <= eval_metrics["acc"] <= 1.0


def smmTest_run_experiment_smoke(tmp_path):
    smmConfig = {
        "name": "unit_test",
        "num_types": 3,
        "seed": 7,
        "synthetic": {
            "num_sequences": 6,
            "num_events": 30,
            "num_types": 3,
            "seed": 7
        },
        "training": {
            "smmWindow_size": 12,
            "stride": 6,
            "batch_size": 4,
            "epochs": 1,
            "lr": 1e-3,
            "delta_weight": 1.0,
            "embed_dim": 8,
            "hidden_dim": 16,
            "backbone": "mlp",
            "mlp_layers": 2,
            "smmMeasure_runtime": False,
            "verbose": False
        }
    }
    from neural_hawkes import smmRun_experiment
    result = smmRun_experiment(smmConfig, device=torch.device("cpu"), output_path=tmp_path / "unit_test.json")
    assert "test_metrics" in result
    assert "loss" in result["test_metrics"]
    assert "rescaling" in result


