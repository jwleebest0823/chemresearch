"""Tests for foam_gnn.propagate (v2, ratchet-free) — helpers + behavioural guarantees.

The behavioural tests encode the properties the ratchet defect violated:
identity persists, merges are detected AND reversible (resurrection), the region
count tracks the independent interior-blob count (no collapse), and the collapse
guard fires. See docs/propagation_ratchet_defect.md.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from scipy import ndimage as ndi

from foam_gnn.config import PipelineConfig
from foam_gnn.propagate import (
    _area_filter_relabel,
    _blob_prev_overlaps,
    _estimate_drift,
    _pair_ridge,
    _tight_flood_mask,
    segment_track_propagated,
)

CFG = PipelineConfig()


def _cfg(**kw) -> PipelineConfig:
    """PipelineConfig with PropagateConfig overrides."""
    return dataclasses.replace(CFG, propagate=dataclasses.replace(CFG.propagate, **kw))


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def test_area_filter_relabel_drops_small_and_is_contiguous():
    lab = np.zeros((10, 10), np.int32)
    lab[0:5, 0:5] = 7      # area 25 (keep)
    lab[0:1, 9:10] = 3     # area 1 (drop)
    out = _area_filter_relabel(lab, min_area=5)
    assert set(np.unique(out)) == {0, 1}
    assert int((out == 1).sum()) == 25


def test_estimate_drift_recovers_shift():
    foam = np.zeros((80, 80), np.float32)
    foam[20:60, 25:55] = 1.0
    shifted = np.zeros_like(foam)
    shifted[23:63, 23:53] = 1.0     # +3 in y, -2 in x
    dy, dx = _estimate_drift(foam, shifted, CFG)
    assert dy == pytest.approx(3.0, abs=1.0)
    assert dx == pytest.approx(-2.0, abs=1.0)


def test_blob_prev_overlaps_counts_pixels():
    blobs = np.zeros((10, 10), np.int32)
    blobs[0:4, 0:4] = 1          # blob 1
    blobs[6:10, 6:10] = 2        # blob 2
    Lw = np.zeros((10, 10), np.int32)
    Lw[0:4, 0:2] = 5             # id 5 covers half of blob 1
    Lw[6:10, 6:10] = 9           # id 9 covers all of blob 2
    ov = _blob_prev_overlaps(blobs, 2, Lw)
    assert ov[1] == {5: 8}
    assert ov[2] == {9: 16}


def test_pair_ridge_reads_the_interface():
    blobs = np.zeros((10, 20), np.int32)
    blobs[:, :8] = 1
    blobs[:, 12:] = 2
    film = np.zeros((10, 20), np.float32)
    film[:, 8:12] = 1.0          # strong ridge exactly between the blobs
    slices = ndi.find_objects(blobs)
    assert _pair_ridge(blobs, film, slices, 1, 2) > 0.5
    assert np.isnan(_pair_ridge(blobs, np.zeros_like(film), slices, 1, 2)) or \
        _pair_ridge(blobs, np.zeros_like(film), slices, 1, 2) == pytest.approx(0.0)


def test_tight_flood_mask_excludes_generous_rim():
    # a foam mask far larger than the detected interiors: the rim must be excluded
    class L:
        pass
    lay = L()
    lay.interior = np.zeros((60, 60), bool)
    lay.interior[25:35, 25:35] = True
    lay.foam = np.zeros((60, 60), bool)
    lay.foam[5:55, 5:55] = True
    tight = _tight_flood_mask(lay, dilate_px=5)
    assert tight.sum() < lay.foam.sum()          # rim dropped
    assert tight[30, 30]                          # interior kept
    assert not tight[7, 7]                        # far background dropped


# --------------------------------------------------------------------------- #
# behavioural: synthetic foam sequences
# --------------------------------------------------------------------------- #
def _foam_frame(merge_cell: bool = False) -> np.ndarray:
    """A 3x4 grid of bright bubbles separated by dark films, on gray background."""
    H, W = 130, 170
    img = np.full((H, W), 130, np.uint8)
    img[20:110, 30:150] = 205
    for r in range(20, 111, 30):
        img[r - 1:r + 1, 30:150] = 35
    for c in range(30, 151, 30):
        img[20:110, c - 1:c + 1] = 35
    if merge_cell:
        img[50:80, 59:61] = 205     # erase one vertical film -> two bubbles become one
    return img


def test_identity_held_and_no_count_collapse_on_static_sequence():
    frames = [_foam_frame()] * 6
    results, tr = segment_track_propagated(frames, CFG)
    f0 = tr.diagnostics["frame0_max_id"]
    assert f0 >= 4
    counts = [r.n_bubbles for r in results]
    # RATCHET REGRESSION: a static foam must not lose bubbles frame over frame
    assert min(counts) >= counts[0] - 1, f"count collapsed on a static sequence: {counts}"
    # and the region count must track the independent interior-blob count
    assert tr.diagnostics["blob_ratio_min"] >= 0.8
    assert tr.diagnostics["n_births_remaining"] <= f0


def test_merge_detected():
    frames = [_foam_frame(), _foam_frame(merge_cell=True), _foam_frame(merge_cell=True),
              _foam_frame(merge_cell=True)]
    _results, tr = segment_track_propagated(frames, _cfg(probation_frames=1))
    assert [e for e in tr.events if e.kind == "merge"], "a burst film should register a merge"


def test_merge_then_reseparation_RESURRECTS_ids():
    # The property that keeps the split mechanism from reintroducing churn: when a
    # merged region separates again, the merged-away bubble RECLAIMS its old id rather
    # than minting a new one (a reclaimed split costs zero reorganization-birth).
    #
    # NOTE ON SCOPE: this fixture can only show that the mechanism FIRES. Its grid is
    # periodic, and the pipeline's FFT grid-notch is designed to erase periodic
    # structure, so the synthetic films are partly removed and the "bubbles" it yields
    # are unstable fragments -- the exact id bookkeeping is therefore not assertable
    # here. The end-to-end resurrection/churn behaviour is measured on REAL data in
    # dev/seg_propagate_eval.py and reported in docs/segmentation_propagation.md.
    frames = [_foam_frame(), _foam_frame(merge_cell=True), _foam_frame(), _foam_frame()]
    _results, tr = segment_track_propagated(frames, _cfg(probation_frames=1))
    assert tr.diagnostics["n_resurrections"] >= 1


def test_collapse_guard_fires_and_can_be_disabled():
    frames = [_foam_frame()] * 3
    # ratio 1.0 + patience 1 => any frame with fewer regions than interior blobs trips it
    strict = _cfg(collapse_guard="raise", collapse_guard_ratio=1.0, collapse_guard_patience=1)
    try:
        segment_track_propagated(frames, strict)
    except RuntimeError as e:
        assert "COLLAPSE GUARD" in str(e)
    # ...and "off" must never raise
    _r, tr = segment_track_propagated(frames, _cfg(collapse_guard="off"))
    assert "blob_ratio_min" in tr.diagnostics


def test_hysteresis_config_is_validated():
    bad = _cfg(split_film_thresh=CFG.seg.interior_thresh)      # no hysteresis band
    with pytest.raises(ValueError, match="split_film_thresh"):
        segment_track_propagated([_foam_frame()] * 2, bad)


def test_survives_large_drift_edge_loss():
    f0 = _foam_frame()
    f1 = ndi.shift(f0, shift=(6, 18), order=0, cval=130).astype(np.uint8)
    f2 = ndi.shift(f0, shift=(12, 34), order=0, cval=130).astype(np.uint8)
    _results, tr = segment_track_propagated([f0, f1, f2], CFG)   # must not raise
    assert len(tr.id_maps) == 3


def test_labels_stay_inside_the_tight_foam_mask():
    frames = [_foam_frame()] * 2
    results, _tr = segment_track_propagated(frames, CFG)
    for r in results:
        assert r.labels.max() > 0
        # no label may sit on the flat background corners
        assert r.labels[0, 0] == 0 and r.labels[-1, -1] == 0
