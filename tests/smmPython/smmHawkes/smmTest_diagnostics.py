import numpy as np

from hawkes.diagnostics import smmKs_test, smmQq_points


def smmTest_ks_test_handles_empty():
    result = smmKs_test(np.array([]))
    assert not result["pass"]


def smmTest_qq_points_shapes():
    residuals = np.linspace(0.1, 5.0, 10)
    empirical, theoretical = smmQq_points(residuals, n_points=5)
    assert empirical.shape == theoretical.shape


