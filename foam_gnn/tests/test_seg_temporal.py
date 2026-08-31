"""Tests for foam_gnn.seg_temporal stratification/coverage on a synthetic table.

Synthetic bubble-frame table with a known split: one large interior bubble that is
trusted throughout, one small near-edge real bubble that never becomes trusted, and
one small near-edge reorganization birth — so coverage and birth-rate per stratum
are analytically checkable.
"""
from __future__ import annotations

import pandas as pd
import pytest

from foam_gnn.config import PipelineConfig
from foam_gnn.seg_temporal import (
    BUBBLE_FRAME_COLUMNS,
    add_strata,
    coverage_by_stratum,
    frame0_coverage_by_stratum,
    headline_summary,
    reorg_birth_by_stratum,
)

CFG = PipelineConfig()


def _table():
    rows = []
    # bubble 1: large interior, trusted all 5 frames
    for f in range(5):
        rows.append(dict(foam="A", session="s", frame=f, bubble_id=1, area=1000.0,
                         distance_to_evap_edge=100.0, is_reorg_origin=False,
                         is_birth_frame=False, is_trusted=True))
    # bubble 2: small near-edge REAL bubble, never trusted, frames 0-1
    for f in range(2):
        rows.append(dict(foam="A", session="s", frame=f, bubble_id=2, area=50.0,
                         distance_to_evap_edge=5.0, is_reorg_origin=False,
                         is_birth_frame=False, is_trusted=False))
    # bubble 100: small near-edge reorganization birth at frame 2
    rows.append(dict(foam="A", session="s", frame=2, bubble_id=100, area=50.0,
                     distance_to_evap_edge=5.0, is_reorg_origin=True,
                     is_birth_frame=True, is_trusted=False))
    return pd.DataFrame(rows)[BUBBLE_FRAME_COLUMNS]


def test_strata_separate_large_interior_from_small_edge():
    t = add_strata(_table(), CFG.seg_eval)
    b1 = t[t["bubble_id"] == 1].iloc[0]
    b2 = t[t["bubble_id"] == 2].iloc[0]
    assert b1["size_bin"] == "large" and b1["dist_bin"] == CFG.seg_eval.n_dist_bins - 1
    assert b2["size_bin"] == "small" and b2["dist_bin"] == 0


def test_coverage_by_stratum():
    t = add_strata(_table(), CFG.seg_eval)
    cov = coverage_by_stratum(t).set_index(["size_bin", "dist_bin"])
    assert cov.loc[("large", CFG.seg_eval.n_dist_bins - 1), "trusted_frac"] == pytest.approx(1.0)
    assert cov.loc[("small", 0), "trusted_frac"] == pytest.approx(0.0)
    assert cov.loc[("small", 0), "trusted_area_frac"] == pytest.approx(0.0)


def test_reorg_birth_rate_by_stratum():
    t = add_strata(_table(), CFG.seg_eval)
    br = reorg_birth_by_stratum(t).set_index(["size_bin", "dist_bin"])
    # small near-edge stratum: 3 bubble-frames, 1 is a birth -> 1/3
    assert br.loc[("small", 0), "birth_rate"] == pytest.approx(1 / 3)
    assert br.loc[("large", CFG.seg_eval.n_dist_bins - 1), "birth_rate"] == pytest.approx(0.0)


def test_frame0_coverage():
    t = add_strata(_table(), CFG.seg_eval)
    f0 = frame0_coverage_by_stratum(t, CFG.seg_eval).set_index(["size_bin", "dist_bin"])
    # only bubbles 1 and 2 are real at frame 0; bubble1 trusted, bubble2 not
    assert f0.loc[("large", f0.index.get_level_values(1).max()), "coverage"] == pytest.approx(1.0)
    assert f0.loc[("small", 0), "coverage"] == pytest.approx(0.0)


def test_headline_summary():
    s = headline_summary(_table())
    assert s["n_bubble_frames"] == 8
    assert s["trusted_frac"] == pytest.approx(5 / 8)
    assert s["birth_rate"] == pytest.approx(1 / 8)
    assert s["reorg_origin_frac"] == pytest.approx(1 / 8)
