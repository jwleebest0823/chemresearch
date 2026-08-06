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


# ------------------ foam-mask coverage regression (docs/foam_mask_coverage.md) ------ #
def _foam_with_weak_lobe() -> np.ndarray:
    """A foam blob whose TOP lobe has sparse films (large bubbles) => low edge density.

    This reproduces the exp3 defect in miniature: the legacy ``mean + k*std`` threshold
    scales with the foam's area fraction and cuts the sparse lobe off as an open bay
    that fill_holes cannot recover.
    """
    img = np.full((320, 320), 160, np.uint8)
    cv2.circle(img, (160, 190), 110, 205, -1)      # dense body
    for y in range(90, 300, 14):                    # many films => high edge density
        cv2.line(img, (50, y), (270, y), 40, 2)
    for x in range(50, 271, 14):
        cv2.line(img, (x, 90), (x, 300), 40, 2)
    cv2.circle(img, (160, 90), 78, 205, -1)         # sparse lobe on top
    for c in ((120, 70), (200, 70), (160, 118)):    # only a few big bubbles
        cv2.circle(img, c, 32, 40, 2)
    return img


def test_li_threshold_recovers_the_sparse_lobe_that_legacy_drops():
    import dataclasses
    cfg = PipelineConfig().boundary
    img = _foam_with_weak_lobe()
    legacy, _d = compute_foam_mask(img, dataclasses.replace(cfg, thresh_mode="mean_k_std"))
    new, _d2 = compute_foam_mask(img, cfg)          # shipped default (li)
    lobe = np.zeros(img.shape, bool)
    lobe[30:70, 130:190] = True                     # inside the sparse top lobe
    assert new[lobe].mean() > legacy[lobe].mean(), (
        "the shipped threshold must cover at least as much of the sparse lobe as legacy"
    )
    assert new.sum() >= legacy.sum()


def test_unknown_thresh_mode_fails_loud():
    import dataclasses
    bad = dataclasses.replace(PipelineConfig().boundary, thresh_mode="nope")
    with pytest.raises(ValueError, match="thresh_mode"):
        compute_foam_mask(_foam_with_weak_lobe(), bad)


def test_foam_mask_clipping_measures_border_coverage():
    from foam_gnn.segmentation import foam_mask_clipping
    free = np.zeros((100, 100), bool)
    free[30:70, 30:70] = True
    assert foam_mask_clipping(free) == 0.0
    assert foam_mask_clipping(np.ones((100, 100), bool)) == pytest.approx(1.0)


def test_clipped_foam_warns_that_dist_to_edge_is_not_evaporation_edge():
    img = np.full((200, 200), 40, np.uint8)         # films everywhere -> foam fills frame
    for y in range(0, 200, 10):
        cv2.line(img, (0, y), (199, y), 205, 6)
    with pytest.warns(RuntimeWarning, match="field of view"):
        compute_foam_mask(img, PipelineConfig().boundary)


# --------- threshold-stability selector (docs/exp1_churn_bisection.md) ------------ #
def _halo_frame() -> np.ndarray:
    """A textured foam blob surrounded by a LOW-CONTRAST HALO.

    Reproduces the late-Foam-A failure in miniature: the halo sits just below the
    legacy threshold and just above Li's, so the mask area is a step function of the
    threshold and a small threshold change floods the mask into the halo.
    """
    img = np.full((260, 260), 150, np.uint8)
    cv2.circle(img, (130, 130), 105, 158, -1)        # faint halo
    cv2.circle(img, (130, 130), 60, 205, -1)         # foam body
    for y in range(70, 191, 10):                      # films -> high edge density
        cv2.line(img, (70, y), (190, y), 45, 2)
    for x in range(70, 191, 10):
        cv2.line(img, (x, 70), (x, 190), 45, 2)
    return img


def test_stability_selector_is_a_noop_when_off_and_validates_its_tolerances():
    import dataclasses
    from foam_gnn.segmentation import _stable_threshold, foam_edge_density
    cfg = PipelineConfig().boundary
    dens = foam_edge_density(_halo_frame(), cfg)
    off = dataclasses.replace(cfg, thresh_stability="off")
    assert _stable_threshold(dens, 12.34, off) == 12.34
    bad = dataclasses.replace(cfg, thresh_stability_eps=0.0)
    with pytest.raises(ValueError, match="thresh_stability_eps"):
        _stable_threshold(dens, 12.34, bad)


def test_stability_selector_steps_off_a_cliff_in_the_density_map():
    """Mechanism test on a CONTROLLED density map (image formation factored out).

    Core at density 100, a wide halo at 60, background at 10. A threshold just below
    the halo floods the mask; stepping up across 60 collapses it. The selector must
    detect that its starting point is on the cliff and climb above the halo.
    """
    from foam_gnn.segmentation import _stable_threshold, _mask_from_density
    cfg = PipelineConfig().boundary
    dens = np.full((400, 400), 10.0)
    cv2.circle(dens, (200, 200), 170, 60.0, -1)      # halo plateau
    cv2.circle(dens, (200, 200), 70, 100.0, -1)      # foam core
    # thr0 must sit within ONE eps step of the cliff: the selector uses a single-step
    # lookahead, so a cliff further away than eps*thr reads as a false plateau. That is
    # a real limitation of the mechanism (it is why eps=0.015 fails on exp1 f197) and is
    # documented in docs/exp1_churn_bisection.md, not papered over.
    thr0 = 59.0                                       # just BELOW the halo -> floods
    flooded = _mask_from_density(dens, thr0, cfg)
    thr = _stable_threshold(dens, thr0, cfg)
    stable = _mask_from_density(dens, thr, cfg)
    assert thr > thr0, "selector did not step up off the cliff"
    assert stable.sum() < 0.5 * flooded.sum(), (
        f"selector failed to shed the halo: {stable.sum()} vs {flooded.sum()}")
    # and it must stop once on the core plateau, not run away to an empty mask
    assert stable.sum() > 0


def test_stability_selector_leaves_a_plateau_frame_untouched(frames):
    """Frames already on a plateau (all GT frames) must be bit-identical."""
    import dataclasses
    cfg = PipelineConfig().boundary
    raw, _d = compute_foam_mask(frames[0], dataclasses.replace(cfg, thresh_stability="off"))
    stab, _d2 = compute_foam_mask(frames[0], cfg)
    assert np.array_equal(raw, stab)
