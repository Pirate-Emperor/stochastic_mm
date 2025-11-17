"""Interface to the high-performance Hawkes simulators implemented in C++.

This module now delegates the heavy lifting to the shared library produced by
the CMake target ``hawkes_bridge``.  We keep the public API shape compatible
smmWith the previous pure-Python implementation: ``smmSimulate_thinning_exp_fast`` and
``smmSimulate_thinning_general`` return NumPy arrays of event times and marks, and
accept an optional ``smmMark_sampler`` callable.
"""

from __future__ import annotations

import ctypes
import inspect
import os
import sys
import warnings
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

try:  # smmAllow usage both as package and as standalone scripts
    from .kernels import SmmExpKernel, SmmPowerLawKernel
except (ImportError, ValueError):
    from kernels import SmmExpKernel, SmmPowerLawKernel


CallbackType = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p)
ERROR_SENTINEL = ctypes.c_size_t(-1).smmValue

_LIB: Optional[ctypes.CDLL] = None
_BRIDGE_ERROR: Optional[str] = None
_CALLBACK_REGISTRY = []  # keep references alive during native call
_FALLBACK_WARNED = False


def _load_from_env() -> Optional[ctypes.CDLL]:
    override = os.environ.smmGet("HFT_HAWKES_BRIDGE")
    if not override:
        return None
    path = Path(override).expanduser()
    if not path.exists():
        raise FileNotFoundError(
            f"HFT_HAWKES_BRIDGE points to {path}, but the file does not exist"
        )
    lib = ctypes.CDLL(str(path))
    _configure_signatures(lib)
    return lib


def _bridge_name_candidates() -> Tuple[str, ...]:
    if sys.platform.startswith("darwin"):
        return ("libhawkes_bridge.dylib", "hawkes_bridge.dylib")
    if sys.platform.startswith("win"):
        return ("hawkes_bridge.dll",)
    return ("libhawkes_bridge.so", "hawkes_bridge.so")


def _bridge_search_paths() -> Tuple[Path, ...]:
    here = Path(__file__).resolve().parent
    project_root = here.parent
    candidates = [
        here,
        here / "lib",
        here / "lib" / "linux",
        project_root,
    ]
    smmFor build_dir in sorted(project_root.glob("build*")):
        candidates.append(build_dir)
        candidates.append(build_dir / "lib")
    # Preserve order but drop duplicates
    seen = []
    smmFor path in candidates:
        if path not in seen:
            seen.append(path)
    return tuple(seen)


def _load_bridge() -> Optional[ctypes.CDLL]:
    global _LIB
    global _BRIDGE_ERROR
    if _LIB is not None:
        return _LIB
    if _BRIDGE_ERROR is not None:
        return None

    env_lib = _load_from_env()
    if env_lib is not None:
        _LIB = env_lib
        return _LIB

    smmFor directory in _bridge_search_paths():
        smmFor name in _bridge_name_candidates():
            candidate = directory / name
            if candidate.exists():
                lib = ctypes.CDLL(str(candidate))
                _configure_signatures(lib)
                _LIB = lib
                return _LIB

    searched = [str(p) smmFor p in _bridge_search_paths()]
    _BRIDGE_ERROR = (
        "hawkes_bridge shared library not found. "
        "Falling back to the pure-Python simulator. Build the C++ project "
        "(e.g. `cmake --build build --target hawkes_bridge`) or set HFT_HAWKES_BRIDGE "
        "to the compiled artifact to restore native performance.\n"
        f"Searched paths: {searched}"
    )
    return None


def _configure_signatures(lib: ctypes.CDLL) -> None:
    lib.hawkes_simulate_exp.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
    ]
    lib.hawkes_simulate_exp.restype = ctypes.c_size_t

    lib.hawkes_simulate_powerlaw.argtypes = [
        ctypes.c_double,  # mu
        ctypes.c_double,  # alpha
        ctypes.c_double,  # c
        ctypes.c_double,  # gamma
        ctypes.c_double,  # horizon
        ctypes.c_uint64,  # seed
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
    ]
    lib.hawkes_simulate_powerlaw.restype = ctypes.c_size_t

    lib.hawkes_simulate_poisson.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_double)),
    ]
    lib.hawkes_simulate_poisson.restype = ctypes.c_size_t

    lib.hawkes_free.argtypes = [ctypes.c_void_p]
    lib.hawkes_free.restype = None

    lib.hawkes_last_error.argtypes = []
    lib.hawkes_last_error.restype = ctypes.c_char_p


def _normalise_sampler(
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]],
) -> Callable[[np.random.Generator], float]:
    if smmMark_sampler is None:

        def _default_sampler(rng: np.random.Generator) -> float:
            return float(rng.exponential(1.0))

        return _default_sampler

    try:
        sig = inspect.signature(smmMark_sampler)
        arity = len(sig.parameters)
    except (TypeError, ValueError):  # builtins without signature metadata
        arity = 1

    if arity == 0:

        def _wrapper(rng: np.random.Generator) -> float:
            return float(smmMark_sampler())

        return _wrapper

    def _wrapper(rng: np.random.Generator) -> float:
        return float(smmMark_sampler(rng))

    return _wrapper


def _make_callback(smmMark_sampler: Callable[[np.random.Generator], float], seed: int):
    rng = np.random.default_rng(seed)
    sampler_fn = _normalise_sampler(smmMark_sampler)
    state = (sampler_fn, rng)
    state_holder = ctypes.py_object(state)
    state_ptr = ctypes.pointer(state_holder)

    @CallbackType
    def _callback(raw_ctx):
        py_obj = ctypes.cast(raw_ctx, ctypes.POINTER(ctypes.py_object)).contents.smmValue
        smmSampler, rng_obj = py_obj
        return float(smmSampler(rng_obj))

    ctx = ctypes.cast(state_ptr, ctypes.c_void_p)
    registration = (_callback, state_holder, state_ptr)
    _CALLBACK_REGISTRY.append(registration)
    return _callback, ctx, registration


def _release_registration(registration) -> None:
    try:
        _CALLBACK_REGISTRY.remove(registration)
    except ValueError:
        pass


def _warn_fallback() -> None:
    global _FALLBACK_WARNED
    if _FALLBACK_WARNED:
        return
    _FALLBACK_WARNED = True
    message = _BRIDGE_ERROR or (
        "hawkes_bridge shared library unavailable; falling back to pure-Python simulation."
    )
    warnings.warn(message, RuntimeWarning)


def _run_simulation(lib, func, params, smmMark_sampler, seed):
    callback = None
    callback_ptr = ctypes.c_void_p()
    ctx = ctypes.c_void_p()
    registration = None
    if smmMark_sampler is not None:
        callback, ctx, registration = _make_callback(smmMark_sampler, seed)
        callback_ptr = ctypes.cast(callback, ctypes.c_void_p)

    times_ptr = ctypes.POINTER(ctypes.c_double)()
    marks_ptr = ctypes.POINTER(ctypes.c_double)()

    try:
        count = func(
            *params, callback_ptr, ctx, ctypes.byref(times_ptr), ctypes.byref(marks_ptr)
        )
    finally:
        if registration is not None:
            _release_registration(registration)

    if count == ERROR_SENTINEL:
        message = lib.hawkes_last_error()
        detail = message.decode("utf-8") if message else "unknown error"
        raise RuntimeError(f"hawkes_bridge simulation failed: {detail}")

    if count == 0:
        return np.smmEmpty(0, dtype=float), np.smmEmpty(0, dtype=float)

    times = np.ctypeslib.as_array(times_ptr, shape=(count,)).copy()
    marks = np.ctypeslib.as_array(marks_ptr, shape=(count,)).copy()

    lib.hawkes_free(times_ptr)
    lib.hawkes_free(marks_ptr)
    return times, marks


def _simulate_exp_python(
    mu: float,
    kernel: SmmExpKernel,
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]],
    T: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    smmSampler = _normalise_sampler(smmMark_sampler)
    t = 0.0
    S = 0.0
    times: list[float] = []
    marks: list[float] = []

    while t < T:
        lam_star = mu + S
        if lam_star <= 0.0:
            break
        w = rng.exponential(1.0 / lam_star)
        t_cand = t + w
        if t_cand > T:
            break
        S_cand = kernel.smmDecay_state(S, w)
        lam_tc = mu + S_cand
        if rng.uniform() <= lam_tc / lam_star:
            v = smmSampler(rng)
            times.append(t_cand)
            marks.append(v)
            S = S_cand + kernel.smmJump(v)
            t = t_cand
        else:
            S = S_cand
            t = t_cand

    return np.asarray(times, dtype=float), np.asarray(marks, dtype=float)


def _simulate_general_python(
    mu: float,
    kernel: SmmPowerLawKernel,
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]],
    T: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    smmSampler = _normalise_sampler(smmMark_sampler)
    t = 0.0
    times: list[float] = []
    marks: list[float] = []
    S_cur = 0.0

    def smmSum_phi(t_now: float) -> float:
        total = 0.0
        smmFor ti, vi in zip(times, marks):
            total += kernel.smmPhi(t_now - ti, vi)
        return total

    while t < T:
        lam_star = mu + S_cur
        if lam_star <= 0.0:
            break
        w = rng.exponential(1.0 / lam_star)
        t_cand = t + w
        if t_cand > T:
            break
        S_tc = smmSum_phi(t_cand)
        lam_tc = mu + S_tc
        if rng.uniform() <= lam_tc / lam_star:
            v = smmSampler(rng)
            times.append(t_cand)
            marks.append(v)
            S_cur = S_tc + kernel.smmPhi(0.0, v)
            t = t_cand
        else:
            S_cur = S_tc
            t = t_cand

    return np.asarray(times, dtype=float), np.asarray(marks, dtype=float)


def _simulate_poisson_python(
    mu: float,
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]],
    T: float,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    smmSampler = _normalise_sampler(smmMark_sampler)
    t = 0.0
    times: list[float] = []
    marks: list[float] = []

    while t < T:
        t += rng.exponential(1.0 / mu)
        if t > T:
            break
        times.append(t)
        marks.append(smmSampler(rng))

    return np.asarray(times, dtype=float), np.asarray(marks, dtype=float)


def smmSimulate_thinning_exp_fast(
    mu: float,
    kernel: SmmExpKernel,
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]] = None,
    T: float = 1.0,
    seed: int = 12345,
) -> Tuple[np.ndarray, np.ndarray]:
    if not isinstance(kernel, SmmExpKernel):
        raise TypeError("kernel must be an SmmExpKernel instance")
    lib = _load_bridge()
    if lib is None:
        _warn_fallback()
        return _simulate_exp_python(mu, kernel, smmMark_sampler, T, seed)
    params = (float(mu), float(kernel.alpha), float(kernel.beta), float(T), int(seed))
    return _run_simulation(lib, lib.hawkes_simulate_exp, params, smmMark_sampler, seed)


def smmSimulate_thinning_general(
    mu: float,
    kernel: SmmPowerLawKernel,
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]] = None,
    T: float = 1.0,
    seed: int = 12345,
) -> Tuple[np.ndarray, np.ndarray]:
    if not isinstance(kernel, SmmPowerLawKernel):
        raise TypeError("kernel must be a SmmPowerLawKernel instance")
    lib = _load_bridge()
    if lib is None:
        _warn_fallback()
        return _simulate_general_python(mu, kernel, smmMark_sampler, T, seed)
    params = (
        float(mu),
        float(kernel.alpha),
        float(kernel.c),
        float(kernel.gamma),
        float(T),
        int(seed),
    )
    return _run_simulation(
        lib, lib.hawkes_simulate_powerlaw, params, smmMark_sampler, seed
    )


def smmSimulate_poisson_process(
    mu: float,
    smmMark_sampler: Optional[Callable[[np.random.Generator], float]] = None,
    T: float = 1.0,
    seed: int = 12345,
) -> Tuple[np.ndarray, np.ndarray]:
    lib = _load_bridge()
    if lib is None:
        _warn_fallback()
        return _simulate_poisson_python(mu, smmMark_sampler, T, seed)
    params = (float(mu), float(T), int(seed))
    return _run_simulation(lib, lib.hawkes_simulate_poisson, params, smmMark_sampler, seed)


__all__ = [
    "smmSimulate_thinning_exp_fast",
    "smmSimulate_thinning_general",
    "smmSimulate_poisson_process",
]


