"""Build a compact Cellpose/Colab upload package.

# WHY THIS EXISTS
`docs/learned_detector_cellpose.md` measured Cellpose-SAM on CPU at ~64 min/frame --
impractical for the decisive test (the full exp3 / Foam C sequence, 99 frames, ~105 h).
This script packages EXACTLY what a Colab GPU notebook needs to run that test, so the
full (gitignored, multi-GB) `data/` tree never has to be uploaded:

  1. the 14 hand-labelled Foam A frames + their GT masks (Task 1/2 baseline + fine-tune)
  2. the full exp3 (Foam C) sequence, unlabelled (Task 3 -- the decisive fragmentation
     test: does a learned detector's region count rise through the sequence the way the
     watershed's does?)
  3. a manifest Colab iterates over, and reference_metrics.json so results can be
     compared without re-deriving the current pipeline's numbers.

Regenerable from `data/` + `groundtruth/` (both present locally, both gitignored) --
nothing here is a new research artifact, so the OUTPUT (`colab_package/`) is gitignored
too. This script lives at the project root (like `label.py`) rather than under `dev/`
(which is entirely gitignored, scratch-only) because it IS meant to be committed and
re-run whenever the underlying data changes.

# DECISION: exp3's own hand-corrected GT (groundtruth/eval/exp3/f000,f001.png) is
DELIBERATELY EXCLUDED from `gt/`, even though it exists locally. It was produced by
DELETING regions from the watershed's own pre-seed (docs/foamc_detection_accuracy.md),
so its recall is 1.0 by construction for the watershed and meaningless for any other
detector. Shipping it invites exactly the naive comparison README.md warns against.

Run:  python build_colab_package.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import imageio.v3 as iio

import dataclasses

from foam_gnn.config import PipelineConfig
from foam_gnn.dataset import EXPERIMENTS, experiment_frame_paths
from foam_gnn.gt_preseed import LABEL_FRAMES, corrected_path
from foam_gnn.io_utils import load_experiment_frames
from foam_gnn.propagate import segment_track_propagated
from foam_gnn.seg_eval import load_gt_frame

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
GT_ROOT = ROOT / "groundtruth"
OUT = ROOT / "colab_package"

EXP1_FRAMES = sorted(idx for dset, exp, idx, note in LABEL_FRAMES if exp == "exp1")
N_EXP3_FRAMES = len(experiment_frame_paths(DATA_ROOT, "exp3"))

# current watershed pipeline's headline number, so Colab can compare without re-deriving
# it (docs/gates_v4_repairs.md:119; also docs/learned_detector_cellpose.md).
FOAM_A_GT_POOLED = {
    "precision": 0.9252, "recall": 0.8818, "f1": 0.9030, "n_frames": 14,
    "note": "current watershed pipeline (propagated), pooled over all 14 hand-corrected "
            "Foam A GT frames at IoU>=0.5. docs/gates_v4_repairs.md line 119.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_exp1_frames() -> None:
    """Copy the raw-frame exports already made for labeling (tolabel/) -- these ARE,
    pixel for pixel, the images the GT masks were drawn on, so copying is exact and
    avoids a second (potentially non-identical) decode path."""
    out_dir = OUT / "frames" / "exp1"
    out_dir.mkdir(parents=True, exist_ok=True)
    for dset, exp, idx, _note in LABEL_FRAMES:
        if exp != "exp1":
            continue
        src = GT_ROOT / "tolabel" / dset / f"{exp}_f{idx:03d}.png"
        if not src.is_file():
            raise FileNotFoundError(f"expected tolabel export missing: {src}")
        (out_dir / f"f{idx:03d}.png").write_bytes(src.read_bytes())
    print(f"  exp1: wrote {len(EXP1_FRAMES)} frames to {out_dir}")


def export_exp3_frames() -> None:
    """Decode + write the FULL exp3 sequence (no GT for most of it -- this is the
    unlabelled decisive-test foam)."""
    out_dir = OUT / "frames" / "exp3"
    out_dir.mkdir(parents=True, exist_ok=True)
    _paths, imgs = load_experiment_frames(DATA_ROOT, "exp3")
    for i, img in enumerate(imgs):
        iio.imwrite(out_dir / f"f{i:03d}.png", img)
    print(f"  exp3: wrote {len(imgs)} frames to {out_dir}")
    assert len(imgs) == N_EXP3_FRAMES


def export_gt() -> dict[int, int]:
    """Copy the 14 Foam A GT masks; verify byte-identity of copy AND that the
    originals were not touched. Returns {frame_index: n_gt_bubbles}."""
    out_dir = OUT / "gt"
    out_dir.mkdir(parents=True, exist_ok=True)
    digests_before: dict[Path, str] = {}
    counts: dict[int, int] = {}
    for dset, exp, idx, _note in LABEL_FRAMES:
        if exp != "exp1":
            continue
        src = corrected_path(GT_ROOT, dset, exp, idx)
        digests_before[src] = sha256(src)
        dst = out_dir / f"{exp}_f{idx:03d}.png"
        dst.write_bytes(src.read_bytes())
        if sha256(dst) != digests_before[src]:
            raise RuntimeError(f"copy is not byte-identical to source: {src} -> {dst}")
        _labels, info = load_gt_frame(src, expected_hw=EXPERIMENTS[exp].image_hw)
        counts[idx] = info["n_labels"]
    for src, digest in digests_before.items():
        if sha256(src) != digest:
            raise RuntimeError(f"SOURCE GT WAS MODIFIED during packaging: {src}")
    print(f"  gt: wrote {len(digests_before)} masks to {out_dir}, "
          f"byte-identity verified (copies AND untouched originals)")
    return counts


def write_manifest(gt_counts: dict[int, int]) -> None:
    label_set = {(exp, idx): dset for dset, exp, idx, _note in LABEL_FRAMES}
    hw = EXPERIMENTS["exp1"].image_hw
    shape_str = f"{hw[0]}x{hw[1]}"
    rows: list[dict] = []
    for idx in EXP1_FRAMES:
        rows.append({
            "exp": "exp1", "frame_index": idx, "image_file": f"frames/exp1/f{idx:03d}.png",
            "gt_file": f"gt/exp1_f{idx:03d}.png", "set": label_set[("exp1", idx)],
            "image_shape": shape_str,
        })
    for idx in range(N_EXP3_FRAMES):
        rows.append({
            "exp": "exp3", "frame_index": idx, "image_file": f"frames/exp3/f{idx:03d}.png",
            "gt_file": "", "set": "none", "image_shape": shape_str,
        })
    path = OUT / "manifest.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["exp", "frame_index", "image_file", "gt_file",
                                          "set", "image_shape"])
        w.writeheader()
        w.writerows(rows)
    print(f"  manifest: {len(rows)} rows -> {path}")


def compute_exp3_watershed_curve() -> tuple[list[dict], str]:
    """The reference curve: the IDENTITY-PROPAGATING pipeline's region count across the
    FULL exp3 sequence (`segment_track_propagated`, `docs/foamc_fragmentation.md`).

    # DECISION: NOT the plain independent per-frame `WatershedSegmenter` -- that was
    tried first and does NOT reproduce the fragmentation (measured: 383 -> ~250,
    declining, worst running-min ratio 1.17x, BELOW the project's own 1.50x guard
    threshold). The pathology is specific to `segment_track_propagated`'s one-marker-
    per-interior-blob invariant seeding the Sato-ridge interior mask -- large bright
    bubbles carry internal shading, the ridge filter reads it as film, and that
    invariant mints a bubble per fragment. The plain per-frame segmenter seeds from
    global h_maxima instead, which does not have this failure mode (consistent with
    `docs/foamc_fragmentation.md` noting h_maxima gives the physically-correct trend).
    So THIS is the curve a learned detector must be compared against, and it needs
    `fragmentation_guard="warn"` (not the default "raise") to run to completion.
    """
    cfg = dataclasses.replace(
        PipelineConfig(),
        propagate=dataclasses.replace(PipelineConfig().propagate, fragmentation_guard="warn"),
    )
    _paths, imgs = load_experiment_frames(DATA_ROOT, "exp3")
    _results, tracking = segment_track_propagated(imgs, cfg)
    series = tracking.diagnostics["n_regions_series"]
    curve = [{"frame_index": i, "n_bubbles": int(n)} for i, n in enumerate(series)]
    for i in range(0, len(curve), 10):
        print(f"    exp3 propagated-pipeline curve: frame {i}/{len(curve)} -> "
              f"{curve[i]['n_bubbles']} regions", flush=True)
    run_min = series[0]
    worst_ratio, worst_i = 1.0, 0
    for i, n in enumerate(series):
        run_min = min(run_min, n)
        if n / run_min > worst_ratio:
            worst_ratio, worst_i = n / run_min, i
    rising = worst_ratio > cfg.propagate.fragmentation_guard_ratio
    verdict = (
        f"MEASURED (not assumed): worst region-count-vs-running-minimum ratio is "
        f"{worst_ratio:.2f}x at frame {worst_i} ({'ABOVE' if rising else 'BELOW'} the "
        f"project's own {cfg.propagate.fragmentation_guard_ratio:.2f}x fragmentation-"
        f"guard threshold). first={series[0]}, last={series[-1]}, min={min(series)}, "
        f"max={max(series)}."
    )
    print(f"  {verdict}")
    return curve, verdict


def write_reference_metrics(gt_counts: dict[int, int], exp3_curve: list[dict],
                             exp3_verdict: str) -> None:
    payload = {
        "foam_a_gt_pooled": FOAM_A_GT_POOLED,
        "foam_a_per_frame_gt_bubble_counts": {
            f"exp1_f{idx:03d}": gt_counts[idx] for idx in EXP1_FRAMES
        },
        "exp3_watershed_region_count_vs_frame": {
            "method": "segment_track_propagated() (identity-propagating pipeline, "
                      "fragmentation_guard='warn' so it runs to completion), "
                      "PipelineConfig() defaults otherwise -- the detector diagnosed in "
                      "docs/foamc_fragmentation.md. Computed fresh for this package. "
                      "NOTE: the plain independent per-frame WatershedSegmenter does "
                      "NOT show this defect (measured separately, not shipped here) -- "
                      "the fragmentation is specific to this pipeline's interior-blob "
                      "seeding, see the # DECISION comment in build_colab_package.py.",
            "verdict": exp3_verdict,
            "curve": exp3_curve,
        },
    }
    path = OUT / "reference_metrics.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"  reference_metrics.json -> {path}")


def main() -> None:
    print("1/5 exp1 frames (copy from tolabel/, exact GT correspondence)")
    export_exp1_frames()
    print("2/5 exp3 frames (full sequence, fresh decode)")
    export_exp3_frames()
    print("3/5 gt masks (copy + byte-identity verification)")
    gt_counts = export_gt()
    print("4/5 manifest.csv")
    write_manifest(gt_counts)
    print("5/5 reference_metrics.json (includes a fresh exp3 propagated-pipeline curve "
          "-- runs segment_track_propagated over all 99 exp3 frames)")
    exp3_curve, exp3_verdict = compute_exp3_watershed_curve()
    write_reference_metrics(gt_counts, exp3_curve, exp3_verdict)
    print("\ndone.")


if __name__ == "__main__":
    main()
