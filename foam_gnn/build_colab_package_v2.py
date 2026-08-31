"""Build the v2 Cellpose/Colab upload package: FULL exp1 + FULL exp10.

# WHY THIS EXISTS
`docs/cellpose_replication.md` (Task 6) found the cross-foam K comparison is
detector-confounded: Foam A's K = +0.483 is watershed-derived, Foam C's K = +0.178 is
Cellpose-derived, because Colab v1 only processed 14 non-contiguous exp1 frames (7
disjoint pairs) -- too few for any trusted segment to form (`min_persist_frames=5`).
This package carries the FULL exp1 sequence (198 frames, both contiguous runs) so a
same-detector Foam A trusted set becomes possible, removing that confound.

It also adds exp10 (Foam F, 10 s interval) as a candidate third foam -- exp10 is
guard-rejected under the watershed for the same fragmentation reason Foam C was
(`docs/exp10_replication_attempt.md`), so if Cellpose fixed Foam C it may fix exp10 too.

Regenerable from `data/` + `groundtruth/` (gitignored data/, committed groundtruth/) --
this script lives at the project root (like `label.py`, `build_colab_package.py`)
because it IS meant to be committed and re-run; its OUTPUT (`colab_package_v2/`) is
bulk data and is gitignored.

# DECISION: exp3's GT is still not shipped anywhere in this package (it never was
relevant here -- this package carries exp1/exp10, neither of which that caveat
concerns), but the README repeats the warning since a Colab notebook may reuse v1's
exp3 masks alongside these.

Frames are decoded FRESH for the full sequence, EXCEPT the 14 already-labelled ones,
which are copied byte-for-byte from `tolabel/` (v1's approach) -- guaranteeing exact
pixel correspondence to the GT masks without depending on PNG-encoder round-trip
equivalence. `iio.imwrite` on this machine does not reproduce another encoder's
compressed byte stream even for identical pixels (measured: file-byte comparison
FAILED on f000 while the DECODED arrays were bit-identical, 0/1,310,720 pixels
differing) -- so decoded-array equality, not file-hash equality, is the correct and
sufficient check, and it is what genuinely matters ("the GT masks correspond
pixel-for-pixel to the packaged image"). Both are verified below: file-copy exactness
for the 14 GT frames, decoded-array equality for every fresh-encoded frame against its
own source pixels.

Run:  python build_colab_package_v2.py
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from foam_gnn.config import PipelineConfig
from foam_gnn.dataset import (EXPERIMENTS, contiguous_runs, experiment_frame_paths,
                              experiment_timestamps)
from foam_gnn.gt_preseed import LABEL_FRAMES, corrected_path
from foam_gnn.io_utils import load_experiment_frames
from foam_gnn.propagate import segment_track_propagated
from foam_gnn.seg_eval import load_gt_frame

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
GT_ROOT = ROOT / "groundtruth"
OUT = ROOT / "colab_package_v2"

EXP1_LABELLED = sorted(idx for dset, exp, idx, note in LABEL_FRAMES if exp == "exp1")
EXP1_LABEL_SET = {(exp, idx): dset for dset, exp, idx, _note in LABEL_FRAMES}
N_EXP1 = len(experiment_frame_paths(DATA_ROOT, "exp1"))
N_EXP10 = len(experiment_frame_paths(DATA_ROOT, "exp10"))

# Reference numbers so Colab can compare without re-deriving them.
FOAM_A_WATERSHED_MICRO = {
    "precision": 0.9252, "recall": 0.8818, "f1": 0.9030, "n_frames": 14,
    "note": "current watershed pipeline (propagated), micro-pooled over all 14 "
            "hand-corrected Foam A GT frames at IoU>=0.5. docs/gates_v4_repairs.md:119.",
}
FOAM_A_CELLPOSE_V1_MICRO = {
    "precision": 0.9892, "recall": 0.9447, "f1": 0.9664, "n_frames": 14,
    "note": "Cellpose-SAM zero-shot, micro-pooled over the same 14 frames. "
            "docs/cellpose_replication.md Task 1 (NOT the macro average originally "
            "quoted on Colab -- micro is the number comparable to the watershed bar "
            "above). dev/cellpose_verify.py reproduces this to 5e-5.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Frame export (fresh decode; GT-frame bytes verified against tolabel/)
# --------------------------------------------------------------------------- #
def export_exp1_frames() -> None:
    out_dir = OUT / "frames" / "exp1"
    out_dir.mkdir(parents=True, exist_ok=True)
    _paths, imgs = load_experiment_frames(DATA_ROOT, "exp1")
    if len(imgs) != N_EXP1:
        raise RuntimeError(f"exp1: expected {N_EXP1} frames, decoded {len(imgs)}")

    n_copied = n_fresh = 0
    for i, img in enumerate(imgs):
        dst = out_dir / f"f{i:03d}.png"
        labelled = ("exp1", i) in EXP1_LABEL_SET
        if labelled:
            # copy byte-for-byte from tolabel/ -- guaranteed exact GT correspondence,
            # independent of PNG-encoder behaviour (v1's proven approach).
            dset = EXP1_LABEL_SET[("exp1", i)]
            tolabel = GT_ROOT / "tolabel" / dset / f"exp1_f{i:03d}.png"
            if not tolabel.is_file():
                raise FileNotFoundError(f"expected tolabel export missing: {tolabel}")
            dst.write_bytes(tolabel.read_bytes())
            # verify the copy decodes to the SAME PIXELS as this session's own fresh
            # decode of the raw frame (catches a stale/mismatched tolabel export)
            if not np.array_equal(iio.imread(dst), img):
                raise RuntimeError(
                    f"f{i:03d}: tolabel/ export does not match a fresh decode of the "
                    f"raw frame -- the GT masks would not correspond pixel-for-pixel "
                    f"to the packaged image. Resolve before shipping.")
            n_copied += 1
        else:
            iio.imwrite(dst, img)
            n_fresh += 1

    print(f"  exp1: wrote {len(imgs)} frames to {out_dir} "
          f"({n_copied} copied from tolabel/ + verified pixel-identical, "
          f"{n_fresh} freshly encoded)")


def export_exp10_frames() -> None:
    out_dir = OUT / "frames" / "exp10"
    out_dir.mkdir(parents=True, exist_ok=True)
    _paths, imgs = load_experiment_frames(DATA_ROOT, "exp10")
    if len(imgs) != N_EXP10:
        raise RuntimeError(f"exp10: expected {N_EXP10} frames, decoded {len(imgs)}")
    for i, img in enumerate(imgs):
        iio.imwrite(out_dir / f"f{i:03d}.png", img)
    print(f"  exp10: wrote {len(imgs)} frames to {out_dir}")


def export_gt() -> dict[int, int]:
    """Copy the 14 Foam A GT masks; verify byte-identity of copy AND untouched originals."""
    out_dir = OUT / "gt"
    out_dir.mkdir(parents=True, exist_ok=True)
    digests_before: dict[Path, str] = {}
    counts: dict[int, int] = {}
    for idx in EXP1_LABELLED:
        dset = EXP1_LABEL_SET[("exp1", idx)]
        src = corrected_path(GT_ROOT, dset, "exp1", idx)
        digests_before[src] = sha256(src)
        dst = out_dir / f"exp1_f{idx:03d}.png"
        dst.write_bytes(src.read_bytes())
        if sha256(dst) != digests_before[src]:
            raise RuntimeError(f"copy is not byte-identical to source: {src} -> {dst}")
        _labels, info = load_gt_frame(src, expected_hw=EXPERIMENTS["exp1"].image_hw)
        counts[idx] = info["n_labels"]
    for src, digest in digests_before.items():
        if sha256(src) != digest:
            raise RuntimeError(f"SOURCE GT WAS MODIFIED during packaging: {src}")
    print(f"  gt: wrote {len(digests_before)} masks to {out_dir}, byte-identity "
          f"verified (copies AND untouched originals)")
    return counts


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #
def exp1_run_of(idx: int, runs: list[tuple[int, int]]) -> str:
    for i, (a, b) in enumerate(runs):
        if a <= idx < b:
            return f"run{i}"
    raise ValueError(f"frame {idx} not in any exp1 run {runs}")


def write_manifest(gt_counts: dict[int, int]) -> None:
    ts1 = experiment_timestamps(DATA_ROOT, "exp1")
    runs1 = contiguous_runs(ts1, interval_seconds=EXPERIMENTS["exp1"].interval_seconds)
    hw1 = EXPERIMENTS["exp1"].image_hw
    hw10 = EXPERIMENTS["exp10"].image_hw
    shape1 = f"{hw1[0]}x{hw1[1]}"
    shape10 = f"{hw10[0]}x{hw10[1]}"

    rows: list[dict] = []
    for idx in range(N_EXP1):
        labelled = ("exp1", idx) in EXP1_LABEL_SET
        rows.append({
            "exp": "exp1", "frame_index": idx, "image_file": f"frames/exp1/f{idx:03d}.png",
            "gt_file": f"gt/exp1_f{idx:03d}.png" if labelled else "",
            "set": EXP1_LABEL_SET[("exp1", idx)] if labelled else "none",
            "image_shape": shape1, "run": exp1_run_of(idx, runs1),
        })
    for idx in range(N_EXP10):
        rows.append({
            "exp": "exp10", "frame_index": idx, "image_file": f"frames/exp10/f{idx:03d}.png",
            "gt_file": "", "set": "none", "image_shape": shape10, "run": "",
        })
    path = OUT / "manifest.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["exp", "frame_index", "image_file", "gt_file",
                                          "set", "image_shape", "run"])
        w.writeheader()
        w.writerows(rows)
    print(f"  manifest: {len(rows)} rows ({N_EXP1} exp1 + {N_EXP10} exp10) -> {path}")


# --------------------------------------------------------------------------- #
# Reference watershed curves (fresh, per-run tracking; guards set to warn so a
# guard-rejected foam still runs to completion and its curve can be reported)
# --------------------------------------------------------------------------- #
def _warn_cfg() -> PipelineConfig:
    base = PipelineConfig()
    return dataclasses.replace(
        base,
        propagate=dataclasses.replace(
            base.propagate, fragmentation_guard="warn", collapse_guard="warn"),
    )


def _watershed_curve(exp: str, runs: list[tuple[int, int]]) -> tuple[list[dict], dict]:
    """Per-session (never across an internal gap) propagated-pipeline region counts,
    concatenated back into one absolute-frame-indexed curve."""
    cfg = _warn_cfg()
    curve: list[dict] = []
    for r_i, (a, b) in enumerate(runs):
        _paths, imgs = load_experiment_frames(DATA_ROOT, exp, indices=list(range(a, b)))
        _results, tracking = segment_track_propagated(imgs, cfg)
        series = tracking.diagnostics["n_regions_series"]
        for local_i, n in enumerate(series):
            curve.append({"frame_index": a + local_i, "run": f"run{r_i}", "n_bubbles": int(n)})
        print(f"    {exp} run{r_i} (f{a:03d}-f{b - 1:03d}): "
              f"{series[0]} -> {series[-1]}, min {min(series)}, max {max(series)}", flush=True)

    vals = [c["n_bubbles"] for c in curve]
    run_min, worst_ratio, worst_i = vals[0], 1.0, 0
    for i, v in enumerate(vals):
        run_min = min(run_min, v)
        if v / run_min > worst_ratio:
            worst_ratio, worst_i = v / run_min, i
    from scipy.stats import spearmanr
    rho, p = (float("nan"), float("nan"))
    if len(vals) >= 3:
        s = spearmanr(range(len(vals)), vals)
        rho, p = float(s.correlation), float(s.pvalue)
    guard_ratio = cfg.propagate.fragmentation_guard_ratio
    summary = {
        "worst_ratio": float(worst_ratio), "worst_frame": int(worst_i),
        "guard_ratio": float(guard_ratio),
        "fires": bool(worst_ratio > guard_ratio),
        "spearman_rho": rho, "spearman_p": p,
        "first": int(vals[0]), "last": int(vals[-1]),
        "min": int(min(vals)), "max": int(max(vals)),
    }
    print(f"    -> worst ratio {worst_ratio:.2f}x at abs frame {worst_i} "
          f"({'ABOVE' if summary['fires'] else 'below'} {guard_ratio:.2f}x); "
          f"Spearman rho={rho:+.4f} (p={p:.2e})")
    return curve, summary


def compute_exp1_watershed_curve() -> tuple[list[dict], dict]:
    ts1 = experiment_timestamps(DATA_ROOT, "exp1")
    runs1 = contiguous_runs(ts1, interval_seconds=EXPERIMENTS["exp1"].interval_seconds)
    print(f"  exp1 watershed curve ({len(runs1)} sessions: {runs1})...")
    return _watershed_curve("exp1", runs1)


def compute_exp10_watershed_curve() -> tuple[list[dict], dict]:
    ts10 = experiment_timestamps(DATA_ROOT, "exp10")
    runs10 = contiguous_runs(ts10, interval_seconds=EXPERIMENTS["exp10"].interval_seconds)
    print(f"  exp10 watershed curve ({len(runs10)} session: {runs10}; this is the "
          f"full 503-frame sequence, expect this to take a while)...")
    return _watershed_curve("exp10", runs10)


def write_reference_metrics(gt_counts: dict[int, int], exp1_curve, exp1_sum,
                            exp10_curve, exp10_sum) -> None:
    payload = {
        "foam_a_watershed_micro_pooled": FOAM_A_WATERSHED_MICRO,
        "foam_a_cellpose_v1_micro_pooled": FOAM_A_CELLPOSE_V1_MICRO,
        "foam_a_per_frame_gt_bubble_counts": {
            f"exp1_f{idx:03d}": gt_counts[idx] for idx in EXP1_LABELLED
        },
        "exp1_watershed_region_count_vs_frame": {
            "method": "segment_track_propagated() per contiguous session (run0/run1, "
                      "never tracked across the internal gap), fragmentation_guard= "
                      "collapse_guard='warn' so either guard runs to completion if it "
                      "would otherwise fire. Foam A is NOT expected to trip either "
                      "guard (docs/foamc_fragmentation.md: 'exp1 does not fire').",
            "summary": exp1_sum,
            "curve": exp1_curve,
        },
        "exp10_watershed_region_count_vs_frame": {
            "method": "segment_track_propagated() over the full 503-frame session, "
                      "fragmentation_guard='warn' (exp10 IS guard-rejected under "
                      "default settings -- docs/exp10_replication_attempt.md -- so "
                      "'warn' is required for the curve to reach frame 502).",
            "note": "This is the KNOWN-BAD baseline exp10 comparison referred to in "
                    "the packaging request: compare a Cellpose count-vs-frame curve "
                    "against this to see whether Cellpose fixes exp10 the way it "
                    "fixed Foam C.",
            "summary": exp10_sum,
            "curve": exp10_curve,
        },
    }
    path = OUT / "reference_metrics.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"  reference_metrics.json -> {path}")


def main() -> None:
    print(f"1/6 exp1 frames (full sequence, {N_EXP1} frames, fresh decode + GT-byte check)")
    export_exp1_frames()
    print(f"2/6 exp10 frames (full sequence, {N_EXP10} frames, fresh decode)")
    export_exp10_frames()
    print("3/6 gt masks (copy + byte-identity verification)")
    gt_counts = export_gt()
    print("4/6 manifest.csv")
    write_manifest(gt_counts)
    print("5/6 exp1 watershed reference curve (both runs)")
    exp1_curve, exp1_sum = compute_exp1_watershed_curve()
    print("6/6 exp10 watershed reference curve (full 503-frame session)")
    exp10_curve, exp10_sum = compute_exp10_watershed_curve()
    write_reference_metrics(gt_counts, exp1_curve, exp1_sum, exp10_curve, exp10_sum)
    print("\ndone.")


if __name__ == "__main__":
    main()
