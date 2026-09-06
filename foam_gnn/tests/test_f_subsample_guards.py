"""The fail-loud guards in the Foam F sampling-interval control actually fire.

`dev/f_subsample_control.py` is a driver, not library code, but three of its guards are
load-bearing for the session's conclusion and are cheap to exercise directly:

* the frame interval is taken from the parsed FILENAME TIMESTAMPS and must equal the
  nominal one -- a sub-sampled series that is not really 30 s/frame would invalidate
  the whole comparison;
* the interval must be uniform, so a hidden acquisition gap cannot masquerade as a
  regular cadence;
* a horizon in seconds must be a whole number of frames at that arm's interval, so no
  arm can be quietly fitted at a horizon it cannot represent.

The driver is loaded by path (it lives in ``dev/``, which is not a package).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DEV = Path(__file__).resolve().parents[1] / "dev" / "f_subsample_control.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("f_subsample_control", DEV)
    m = importlib.util.module_from_spec(spec)
    sys.modules["f_subsample_control"] = m
    spec.loader.exec_module(m)
    return m


def _times(n: int, dt: float) -> np.ndarray:
    return np.arange(n, dtype=float) * dt


def test_arm_indices_stride_and_phase(mod):
    """Every third frame from the window, per phase, with nothing outside it."""
    lo, hi = mod.WINDOW
    for phase in (0, 1, 2):
        idx = mod.arm_indices(3, phase)
        assert idx[0] == lo + phase
        assert idx[-1] <= hi
        assert all(b - a == 3 for a, b in zip(idx[:-1], idx[1:]))
    assert mod.arm_indices(1, 0) == list(range(lo, hi + 1))


def test_interval_is_measured_not_assumed(mod):
    """A 10 s series sub-sampled by 3 measures 30 s; the guard accepts it."""
    t = _times(300, 10.0)
    v = mod.verify_interval(t, list(range(0, 226, 3)), 30.0, "sub")
    assert v["dt_median_s"] == pytest.approx(30.0)
    assert v["n_frames"] == 76
    assert v["span_s"] == pytest.approx(2250.0)


def test_wrong_interval_fails_loud(mod):
    """Claiming 30 s for a series that is really 10 s must stop the run."""
    t = _times(300, 10.0)
    with pytest.raises(SystemExit, match="median frame interval"):
        mod.verify_interval(t, list(range(0, 226)), 30.0, "bad")


def test_non_uniform_interval_fails_loud(mod):
    """A hidden acquisition gap must not pass as a regular cadence."""
    t = _times(50, 10.0)
    t[20:] += 45.0                       # a 45 s stall in the middle
    with pytest.raises(SystemExit, match="not uniform"):
        mod.verify_interval(t, list(range(0, 50)), 10.0, "gapped")


def test_horizon_must_be_a_whole_number_of_frames(mod):
    """A 30 s horizon cannot be fitted on a 40 s/frame series -- fail, never round."""
    tr = pd.DataFrame(columns=mod.TRUSTED_COLUMNS)
    with pytest.raises(SystemExit, match="not a whole number"):
        mod.fit_arm(tr, 40.0, "impossible")
