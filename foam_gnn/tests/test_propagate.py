"""Tests for foam_gnn.propagate — deterministic helpers + an integration smoke test.

The helpers (border-film, union-find, drift, relabel) are checked exactly; the full
propagating segmenter is run on a synthetic foam sequence to verify it holds identity
(few births on a static sequence) and detects a genuine merge.
"""
from __future__ import annotations

import numpy as np
import pytest

from foam_gnn.config import PipelineConfig
from foam_gnn.propagate import (
    _area_filter_relabel,
    _estimate_drift,
    _pair_border_film,
    _UF,
    segment_track_propagated,
)

CFG = PipelineConfig()


def test_union_find():
    uf = _UF()
    uf.union(1, 2)
    uf.union(2, 3)
    assert uf.find(1) == uf.find(3)
    assert uf.find(4) != uf.find(1)


def test_area_filter_relabel_drops_small_and_is_contiguous():
    lab = np.zeros((10, 10), np.int32)
    lab[0:5, 0:5] = 7      # area 25 (keep)
    lab[0:1, 9:10] = 3     # area 1 (drop)
    out = _area_filter_relabel(lab, min_area=5)
    assert set(np.unique(out)) == {0, 1}
    assert int((out == 1).sum()) == 25


def test_pair_border_film_high_vs_low():
    # two regions side by side; film HIGH along their border, LOW elsewhere
    lab = np.zeros((10, 20), np.int32)
    lab[:, :10] = 1
    lab[:, 10:] = 2
    film = np.zeros((10, 20), np.float32)
    film[:, 9:11] = 1.0     # strong ridge on the 1|2 border
    stats = _pair_border_film(lab, film)
    assert (1, 2) in stats
    mean_film, n = stats[(1, 2)]
    assert mean_film > 0.5 and n >= 10


def test_estimate_drift_recovers_shift():
    foam = np.zeros((80, 80), np.float32)
    foam[20:60, 25:55] = 1.0
    shifted = np.zeros_like(foam)
    shifted[23:63, 23:53] = 1.0     # moved +3 in y, -2 in x
    dy, dx = _estimate_drift(foam, shifted, CFG)
    assert dy == pytest.approx(3.0, abs=1.0)
    assert dx == pytest.approx(-2.0, abs=1.0)


# --------------------------------------------------------------------------- #
# Integration: synthetic foam sequence
# --------------------------------------------------------------------------- #
def _foam_frame(merge_cell: bool = False) -> np.ndarray:
    """A 3x4 grid of bright bubbles separated by dark films, on gray background."""
    H, W = 130, 170
    img = np.full((H, W), 130, np.uint8)
    img[20:110, 30:150] = 205                       # bright bubble interiors
    for r in range(20, 111, 30):                    # horizontal films
        img[r - 1:r + 1, 30:150] = 35
    for c in range(30, 151, 30):                    # vertical films
        img[20:110, c - 1:c + 1] = 35
    if merge_cell:
        img[50:80, 59:61] = 205                     # erase one vertical film -> merge
    return img


def test_propagated_holds_identity_and_low_births():
    frames = [_foam_frame(), _foam_frame(), _foam_frame()]     # static sequence
    results, tr = segment_track_propagated(frames, CFG)
    assert len(results) == 3 and len(tr.id_maps) == 3
    f0 = tr.diagnostics["frame0_max_id"]
    assert f0 >= 4                                              # grid segmented into several bubbles
    # identity held: far fewer than 1 reorganization-birth per bubble per later frame
    assert tr.diagnostics["n_births_remaining"] <= f0
    # correspondence + events are well-formed
    assert set(["frame", "bubble_id", "area_px", "cx", "cy"]).issubset(tr.correspondence.columns)


def test_propagated_detects_merge():
    frames = [_foam_frame(), _foam_frame(merge_cell=True)]
    _results, tr = segment_track_propagated(frames, CFG)
    merges = [e for e in tr.events if e.kind == "merge"]
    # dissolving a film between two established bubbles should register as a merge
    assert len(merges) >= 1
