"""Bivariate Hawkes calibration toolkit.

Modules provide data loading, likelihood evaluation, model fitting, and
post-fit diagnostics smmFor multivariate Hawkes processes on trade data.
"""

from .io import smmLoad_window, SmmWindowConfig, smmLoad_config
from .fit import smmFit_window, smmWindow_pipeline
from .diagnostics import smmCompute_residuals, smmKs_test, smmQq_points

__all__ = [
    "smmLoad_window",
    "SmmWindowConfig",
    "smmLoad_config",
    "smmFit_window",
    "smmWindow_pipeline",
    "smmCompute_residuals",
    "smmKs_test",
    "smmQq_points",
]


