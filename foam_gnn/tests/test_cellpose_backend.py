"""Known-answer tests for the Cellpose backend + the Theil-Sen scalability cap.

These are constructed cases with hand-computable answers, not smoke tests: the
foam-mask restriction is the one post-processing step the learned detector depends
on, so its behaviour is pinned rather than trusted.
"""
from __future__ import annotations

import numpy as np
import pytest

from foam_gnn.cellpose_backend import count_trend_guard, restrict_to_foam_mask
from foam_gnn.modeling import THEILSEN_MAX_N, k_through_origin


# --------------------------------------------------------------------------- #
# restrict_to_foam_mask
# --------------------------------------------------------------------------- #
def _three_objects():
    """A 20x30 frame: object 1 fully inside, 2 fully outside, 3 straddling 50/50."""
    labels = np.zeros((20, 30), np.int32)
    labels[2:6, 2:6] = 1          # 16 px, all inside
    labels[2:6, 22:26] = 2        # 16 px, all outside
    labels[10:14, 13:17] = 3      # 16 px, half inside (cols 13-14 in, 15-16 out)
    foam = np.zeros((20, 30), bool)
    foam[:, :15] = True
    return labels, foam


def test_fully_outside_object_is_dropped_and_inside_kept():
    labels, foam = _three_objects()
    out, info = restrict_to_foam_mask(labels, foam, min_overlap_frac=0.5)
    kept_at_1 = out[3, 3]
    assert kept_at_1 > 0                       # the inside object survives
    assert out[3, 23] == 0                     # the outside object is gone
    assert info["n_in"] == 3
    assert info["n_dropped_outside"] >= 1


def test_straddling_object_follows_the_majority_vote():
    """Object 3 is exactly 50% inside -> kept at frac<=0.5, dropped above."""
    labels, foam = _three_objects()
    kept_half, _ = restrict_to_foam_mask(labels, foam, min_overlap_frac=0.5)
    assert (kept_half[10:14, 13:15] > 0).all()          # 0.5 >= 0.5 -> kept
    dropped, _ = restrict_to_foam_mask(labels, foam, min_overlap_frac=0.6)
    assert (dropped[10:14, 13:17] == 0).all()           # 0.5 < 0.6 -> dropped


def test_output_is_contiguously_relabeled():
    labels, foam = _three_objects()
    out, info = restrict_to_foam_mask(labels, foam, min_overlap_frac=0.5)
    present = sorted(int(v) for v in np.unique(out) if v > 0)
    assert present == list(range(1, len(present) + 1))
    assert info["n_out"] == len(present)


def test_min_area_filter_is_off_by_default_and_works_when_set():
    labels, foam = _three_objects()
    _out, info_off = restrict_to_foam_mask(labels, foam)
    assert info_off["n_dropped_small"] == 0
    _out2, info_on = restrict_to_foam_mask(labels, foam, min_area_px=100)
    assert info_on["n_out"] == 0                        # every object is 16 px


def test_empty_and_shape_guards():
    labels, foam = _three_objects()
    out, info = restrict_to_foam_mask(np.zeros_like(labels), foam)
    assert info["n_out"] == 0 and out.max() == 0
    with pytest.raises(ValueError):
        restrict_to_foam_mask(labels, foam[:, :10])
    with pytest.raises(ValueError):
        restrict_to_foam_mask(labels, foam, min_overlap_frac=0.0)


# --------------------------------------------------------------------------- #
# count_trend_guard — must agree with propagate.py's inline criterion
# --------------------------------------------------------------------------- #
def test_guard_fires_on_a_sustained_rise():
    # running min 100; 160 > 1.5*100 for 3 consecutive frames -> fires
    g = count_trend_guard([100, 110, 160, 165, 170], ratio=1.5, patience=3)
    assert g["fires"] and g["first_fire_frame"] == 4


def test_guard_silent_on_a_monotone_decline():
    g = count_trend_guard([555, 500, 400, 300, 221], ratio=1.5, patience=3)
    assert not g["fires"]
    assert g["worst_ratio"] == pytest.approx(1.0)
    assert g["spearman_rho"] < -0.9


def test_guard_ignores_a_brief_spike_shorter_than_patience():
    g = count_trend_guard([100, 200, 200, 90, 80], ratio=1.5, patience=3)
    assert not g["fires"]              # only 2 consecutive frames above
    assert g["worst_ratio"] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# Theil-Sen scalability cap (must not perturb sub-cap results)
# --------------------------------------------------------------------------- #
def test_theilsen_under_cap_is_unchanged_by_the_subsample_path():
    rng = np.random.default_rng(0)
    n = 500
    x = rng.uniform(-8, 8, n)
    y = 0.35 * x + rng.normal(0, 0.01, n)
    assert n < THEILSEN_MAX_N
    k = k_through_origin(x, y, "theilsen")
    assert k == pytest.approx(0.35, abs=0.02)


def test_theilsen_above_cap_subsamples_instead_of_exhausting_memory():
    """Foam C's real h=1 fit is n=26,712, which needs 5.7 GB uncapped."""
    rng = np.random.default_rng(1)
    n = THEILSEN_MAX_N + 2_000
    x = rng.uniform(-8, 8, n)
    y = 0.35 * x + rng.normal(0, 0.01, n)
    k = k_through_origin(x, y, "theilsen")       # MemoryError without the cap
    assert np.isfinite(k)
    assert k == pytest.approx(0.35, abs=0.02)    # subsample still recovers the answer


def test_theilsen_cap_is_deterministic():
    rng = np.random.default_rng(2)
    n = THEILSEN_MAX_N + 1_000
    x = rng.uniform(-8, 8, n)
    y = 0.5 * x + rng.normal(0, 0.05, n)
    assert k_through_origin(x, y, "theilsen") == k_through_origin(x, y, "theilsen")


def test_cap_sits_above_foam_A_so_published_numbers_cannot_move():
    """Foam A's largest von Neumann fit is n=7,106 (docs/correctness_audit.md D1)."""
    assert THEILSEN_MAX_N > 7_106


def test_other_estimators_are_untouched_by_the_cap():
    rng = np.random.default_rng(3)
    n = THEILSEN_MAX_N + 100
    x = rng.uniform(-8, 8, n)
    y = 0.4 * x
    assert k_through_origin(x, y, "ls") == pytest.approx(0.4, abs=1e-9)
    assert k_through_origin(x, y, "robust") == pytest.approx(0.4, abs=1e-9)
