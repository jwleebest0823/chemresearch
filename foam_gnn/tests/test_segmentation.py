"""
Smoke tests for MODULE 1 (segmentation) + foundation (config/guards/io_utils).

Goal: confirm the module executes end-to-end on the 5 sample frames and produces
sane outputs, that input guards fail loud, and that backend stubs behave. These
are smoke / contract tests, not a scientific validation of segmentation quality.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from foam_gnn.config import DataConfig, PipelineConfig
from foam_gnn.guards import check_array
from foam_gnn.io_utils import list_experiment_frames, load_frame
from foam_gnn.segmentation import (
    SegmentationResult,
    SAMSegmenter,
    build_segmenter,
    compute_foam_mask,
    flag_suspicious_vertices,
    preprocess,
    qc_overlay,
)


# --------------------------- foundation --------------------------- #
def test_list_experiment_frames(cfg):
    found = list_experiment_frames(cfg.data)
    assert set(found) == {"samples"}
    assert len(found["samples"]) == 5


def test_load_frame_shape_dtype(frames):
    for f in frames:
        assert f.dtype == np.uint8
        assert f.shape == (1024, 1280)


def test_load_frame_missing_raises(cfg, tmp_path):
    with pytest.raises(FileNotFoundError):
        load_frame(tmp_path / "nope.jpg", cfg.data)


def test_enforce_shape_raises(cfg, tmp_path):
    bad = tmp_path / "small.jpg"
    cv2.imwrite(str(bad), np.zeros((32, 32, 3), np.uint8))
    with pytest.raises(ValueError):
        load_frame(bad, cfg.data)


def test_check_array_guards():
    check_array("ok", np.zeros((4, 4), np.uint8), ndim=2, dtype=np.uint8)
    with pytest.raises(TypeError):
        check_array("not_array", [1, 2, 3])
    with pytest.raises(ValueError):
        check_array("bad_ndim", np.zeros((4, 4)), ndim=3)
    with pytest.raises(ValueError):
        check_array("bad_shape", np.zeros((4, 5)), shape=(4, 4))
    with pytest.raises(ValueError):
        check_array("nan", np.array([np.nan, 1.0]), finite=True)


# --------------------------- preprocessing / boundary --------------------------- #
def test_preprocess_contract(frames):
    out = preprocess(frames[0], PipelineConfig().preproc)
    assert out.shape == frames[0].shape and out.dtype == np.uint8


def test_foam_mask_contract(frames):
    mask, dist = compute_foam_mask(frames[0], PipelineConfig().boundary)
    assert mask.dtype == bool and mask.shape == frames[0].shape
    frac = mask.mean()
    assert 0.05 < frac < 0.60, f"implausible foam fraction {frac:.3f}"
    assert np.isfinite(dist).all() and dist.min() >= 0 and dist.max() > 0


# --------------------------- full segmentation --------------------------- #
def test_segment_result_contract(results, sample_paths):
    for res, path in zip(results, sample_paths):
        assert isinstance(res, SegmentationResult)
        check_array("labels", res.labels, ndim=2, dtype=np.int32, nonneg=True)
        assert res.labels.shape == (1024, 1280)
        # contiguous labels 0..n
        assert set(np.unique(res.labels)) == set(range(res.n_bubbles + 1))
        assert res.n_bubbles == int(res.labels.max())
        assert np.isfinite(res.dist_to_edge).all()
        assert 0.05 < res.meta["foam_area_frac"] < 0.60


def test_segment_bubble_counts_plausible(results):
    counts = [r.n_bubbles for r in results]
    # 5 frames span early(dense)->late(coarse); each must be in a believable range
    assert all(20 <= c <= 400 for c in counts), counts
    # coarsening: the last frame should not have more bubbles than the first
    assert counts[-1] <= counts[0], counts


def test_plateau_three_way_majority(results):
    # Plateau sanity: most detected junctions should be 3-way, so the (order-based)
    # suspicious flag should fire on only a minority — i.e. it is actionable, not noise.
    verts = flag_suspicious_vertices(results[0].labels)
    assert len(verts) > 10
    frac3 = np.mean([v["order"] == 3 for v in verts])
    assert frac3 > 0.70, f"only {frac3:.2f} of junctions are 3-way"
    frac_suspicious = np.mean([v["suspicious"] for v in verts])
    assert frac_suspicious < 0.30, f"order-based suspicious rate too high: {frac_suspicious:.2f}"
    # required keys present
    assert set(verts[0]) >= {"y", "x", "order", "suspicious", "reason", "angle_dev_deg", "angle_flag"}


def test_qc_overlay_contract(frames, results):
    ov = qc_overlay(frames[0], results[0])
    assert ov.shape == (1024, 1280, 3) and ov.dtype == np.uint8


# --------------------------- backends --------------------------- #
def test_unknown_backend_raises():
    cfg = PipelineConfig()
    object.__setattr__(cfg.seg, "backend", "does_not_exist")
    with pytest.raises(ValueError):
        build_segmenter(cfg)


def test_sam_stub_raises(frames):
    cfg = PipelineConfig()
    with pytest.raises(NotImplementedError):
        SAMSegmenter(cfg).segment(frames[0])
