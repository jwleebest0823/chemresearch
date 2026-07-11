"""Tests for foam_gnn.seg_eval on a synthetic GT/prediction with KNOWN errors.

The predicted map deliberately: matches 1 large bubble exactly, over-segments 1
(split), under-segments 2 (merge), and misses the small bubbles — so precision/
recall, split/merge, and size-stratified recall are all analytically checkable.
"""
from __future__ import annotations

import numpy as np
import pytest

from foam_gnn.config import PipelineConfig
from foam_gnn.seg_eval import (
    bubble_table,
    detection_metrics,
    evaluate_frame,
    iou_contingency,
    load_gt_frame,
    match_hungarian,
    relabel_sequential,
    split_merge_diagnostics,
    assign_strata,
    stratified_detection,
)

CFG = PipelineConfig()


def _gt():
    g = np.zeros((100, 100), np.int32)
    g[10:30, 10:30] = 1     # large, area 400
    g[10:30, 40:60] = 2     # large, area 400
    g[50:60, 50:60] = 3     # small, area 100 (missed)
    g[70:80, 10:20] = 4     # small, area 100 (merged)
    g[70:80, 25:35] = 5     # small, area 100 (merged)
    return g


def _pred():
    p = np.zeros((100, 100), np.int32)
    p[10:30, 10:30] = 1     # exact match of GT1  (IoU 1.0)
    p[10:30, 40:52] = 2     # 60% of GT2  (IoU 0.6, matched) -> split part A
    p[10:30, 52:60] = 3     # 40% of GT2  (FP) -> split part B
    p[70:80, 10:35] = 4     # covers GT4 AND GT5 -> merge (FP)
    return p


def test_iou_contingency_values():
    iou, ag, ap = iou_contingency(relabel_sequential(_gt()), relabel_sequential(_pred()))
    assert iou.shape == (5, 4)
    assert iou[0, 0] == pytest.approx(1.0)          # GT1 vs pred1
    assert iou[1, 1] == pytest.approx(0.6)          # GT2 vs predA (240/400)
    assert iou[3, 3] == pytest.approx(100 / 250)    # GT4 vs merged pred (0.4)


def test_detection_precision_recall():
    iou, _, _ = iou_contingency(relabel_sequential(_gt()), relabel_sequential(_pred()))
    det = detection_metrics(iou, (0.5,)).iloc[0]
    assert det["tp"] == 2 and det["fp"] == 2 and det["fn"] == 3
    assert det["precision"] == pytest.approx(0.5)   # 2 / 4
    assert det["recall"] == pytest.approx(0.4)      # 2 / 5


def test_hungarian_is_one_to_one():
    iou, _, _ = iou_contingency(relabel_sequential(_gt()), relabel_sequential(_pred()))
    matches, un_gt, un_pred = match_hungarian(iou, 0.5)
    gts = [m[0] for m in matches]
    preds = [m[1] for m in matches]
    assert len(gts) == len(set(gts)) and len(preds) == len(set(preds))
    assert len(matches) == 2


def test_split_and_merge_detected():
    gt, pred = relabel_sequential(_gt()), relabel_sequential(_pred())
    from foam_gnn.seg_eval import gt_foam_distance
    tab = bubble_table(gt, gt_foam_distance(gt))
    tab = assign_strata(tab, CFG.seg_eval)
    sm, totals = split_merge_diagnostics(gt, pred, tab, CFG.seg_eval)
    assert totals["split_rate"] == pytest.approx(1 / 5)     # only GT2 split
    assert totals["merge_rate"] == pytest.approx(2 / 5)     # GT4 + GT5 merged


def test_stratified_recall_separates_large_from_small():
    fe = evaluate_frame(_gt(), _pred(), CFG, exp="t", frame_index=0)
    strat = fe.stratified_recall
    # the size bin holding the two large (matched) bubbles has recall 1.0
    assert (strat.loc[strat["size_bin"] == "large", "recall"] == 1.0).all()
    # some stratum (the small missed/merged bubbles) has recall 0
    assert (strat["recall"] == 0.0).any()
    assert fe.detection.set_index("iou_threshold").loc[0.5, "recall"] == pytest.approx(0.4)


def test_gt_loader_roundtrip_and_shape_check(tmp_path):
    import imageio.v3 as iio
    g = _gt().astype(np.uint16)
    p = tmp_path / "f000.png"
    iio.imwrite(p, g)
    labels, info = load_gt_frame(p, expected_hw=(100, 100))
    assert info["n_labels"] == 5
    assert set(np.unique(labels)) == {0, 1, 2, 3, 4, 5}
    with pytest.raises(ValueError):
        load_gt_frame(p, expected_hw=(128, 128))   # wrong shape -> fail loud
