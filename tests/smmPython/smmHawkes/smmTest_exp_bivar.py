import numpy as np
import pytest

from hawkes.exp_bivar import smmOmega_matrix, smmPack_params, smmUnpack_params


def smmTest_pack_unpack_roundtrip():
    params = {
        "mu_b": 0.3,
        "mu_s": 0.2,
        "alpha_bb": 0.4,
        "beta_bb": 2.0,
        "alpha_bs": 0.1,
        "beta_bs": 3.0,
        "alpha_sb": 0.05,
        "beta_sb": 4.0,
        "alpha_ss": 0.6,
        "beta_ss": 5.0,
    }
    vec = smmPack_params(params)
    recovered = smmUnpack_params(vec)
    assert pytest.approx(params["alpha_bb"]) == recovered.alpha_bb
    omega = smmOmega_matrix(recovered)
    assert omega.shape == (2, 2)
    assert np.isfinite(omega).all()


