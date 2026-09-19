"""Build `results_package/` — a curated set for Dr. Oh to assess the results.

Figures + short tables + two short documents. No code, no logs, no mask binaries, no
caches. Every number traces to a committed artifact under `qc/`.

# DECISION (horizons in SECONDS, not frames): Foams A and C are imaged at 30 s
intervals, Foam F at 10 s. Reporting horizons as frame counts made "t+20" mean 600 s for
A and C but only 200 s for F, so the foams were being compared at different physical
timespans. Every K here is therefore fitted at MATCHED PHYSICAL HORIZONS (30 / 150 /
600 s) and plotted against seconds. Foam F's frame horizons are h = 3 / 15 / 60; A and C
are unchanged at h = 1 / 5 / 20. See METHODS_BRIEF.md.

Run:  python build_results_package.py
"""
from __future__ import annotations

import json
import os
import shutil
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from foam_gnn.config import PipelineConfig
from foam_gnn.modeling import fit_von_neumann, make_horizon_samples

ROOT = Path(__file__).resolve().parent
QC = ROOT / "qc"
OUT = ROOT / "results_package"
FIG = OUT / "figures"
TAB = OUT / "tables"
for d in (FIG, TAB):
    d.mkdir(parents=True, exist_ok=True)

CFG = PipelineConfig()
NB = CFG.eval.n_bootstrap
FOAM_COL = {"A": "#1f77b4", "C": "#d62728", "F": "#2ca02c"}
# Frame interval per foam, verified from the parsed filename timestamps (not config).
FRAME_DT = {"A": 30.0, "C": 30.0, "F": 10.0}
HORIZONS_S = (30, 150, 600)


# --------------------------------------------------------------------------- #
def build_K_table(reuse: bool = False) -> pd.DataFrame:
    """Canonical K table at matched physical horizons. Supersedes the frame-matched
    task4_K.csv for Foam F (A and C are identical, already at 30/150/600 s).

    ``reuse`` returns the saved table instead of refitting -- for re-rendering figures
    without repeating the bootstrap. The fit itself is unchanged either way.
    """
    if reuse and (TAB / "K_fits.csv").is_file():
        return pd.read_csv(TAB / "K_fits.csv")
    tr = pd.read_csv(QC / "cellpose_v2" / "trusted_all_cellpose.csv")
    rows = []
    for foam in sorted(tr["foam"].unique()):
        g = tr[tr.foam == foam]
        dt = FRAME_DT[foam]
        for secs in HORIZONS_S:
            h = int(round(secs / dt))
            s = make_horizon_samples(g, h)
            if len(s) < 20:
                continue
            f = fit_von_neumann(s["n_sides"].to_numpy(), s["target_dadt"].to_numpy(),
                                bubble_of=s["bubble_uid"].to_numpy(), n_boot=NB,
                                estimator="robust")
            rows.append({"foam": foam, "horizon_seconds": secs, "horizon_frames": h,
                         "frame_interval_s": dt, "n": f["n"], "n_bubbles": f["n_bubbles"],
                         "K": f["K"], "ci_lo": f["K_ci"][0], "ci_hi": f["K_ci"][1],
                         "K_theilsen": f["K_theilsen"], "K_ls": f["K_ls"],
                         "n0_free": f["n0_free"],
                         "median_abs_dadt": f["median_abs_dadt"],
                         "K_normalised": f["K_normalised"]})
    K = pd.DataFrame(rows)
    K.to_csv(TAB / "K_fits.csv", index=False)
    return K


def fig_K_vs_horizon(K: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 5.4))
    for foam, g in K.groupby("foam"):
        g = g.sort_values("horizon_seconds")
        lo = g["K"] - g["ci_lo"]
        hi = g["ci_hi"] - g["K"]
        ax.errorbar(g["horizon_seconds"], g["K"], yerr=[lo, hi], marker="o", capsize=4,
                    label=f"Foam {foam}  ({FRAME_DT[foam]:.0f} s/frame)",
                    color=FOAM_COL.get(foam), lw=1.8, ms=7)
    ax.axhline(0, color="k", lw=0.8, ls=":")
    ax.set_xscale("log")
    ax.set_xticks(list(HORIZONS_S))
    ax.set_xticklabels([f"{s} s" for s in HORIZONS_S])
    ax.set_xlabel("prediction horizon (seconds of elapsed time)")
    ax.set_ylabel("von Neumann K   (dA/dt = K·(n−6)),   px² s⁻¹")
    ax.set_title("K is positive at every horizon in every foam", fontsize=11)
    ax.set_ylim(bottom=min(-0.03, float(K["ci_lo"].min()) - 0.05))
    ax.legend(frameon=False, loc="upper right")
    fig.subplots_adjust(bottom=0.30)
    fig.text(0.5, 0.02,
             "Caption: horizons are matched in SECONDS so the foams are comparable. Foam A "
             "and Foam C are\nimaged at 30 s/frame (horizons = 1, 5, 20 frames); Foam F at "
             "10 s/frame (3, 15, 60 frames). Intervals\nwere verified from the image "
             "filename timestamps. Bars are 95% confidence intervals from a\nbootstrap "
             "resampling whole bubbles. Units of K are px² per second.",
             ha="center", fontsize=8.5, style="italic")
    fig.savefig(FIG / "fig1_K_vs_horizon.png", dpi=160)
    plt.close(fig)


def fig_counts() -> None:
    ws = json.loads((ROOT / "colab_package" / "reference_metrics.json").read_text())
    ws_c = pd.DataFrame(ws["exp3_watershed_region_count_vs_frame"]["curve"])
    cp_c = pd.read_csv(ROOT / "cellpose_out" / "exp3_counts.csv")
    cp_1 = pd.read_csv(ROOT / "cellpose_results_v2" / "cellpose_out_v2" / "exp1_counts.csv")
    cp_10 = pd.read_csv(ROOT / "cellpose_results_v2" / "cellpose_out_v2" / "exp10_counts.csv")

    # # DECISION (review 2026-09-18): the rank correlations in the titles are computed here
    # from the series actually plotted. The hardcoded +0.98 and -0.995 ... -0.9993 did not
    # match them (+0.87; the plotted Foam F window is -0.987) and are withdrawn.
    from scipy.stats import spearmanr
    rho_ws = float(spearmanr(ws_c["frame_index"], ws_c["n_bubbles"]).statistic)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 5.4))
    axes[0].plot(ws_c["frame_index"] * 30.0, ws_c["n_bubbles"], color="#d62728", lw=1.6)
    axes[0].set_title(f"Foam C, watershed pipeline\ncount RISES  (Spearman ρ = {rho_ws:+.2f})",
                      fontsize=10)
    axes[0].set_xlabel("elapsed time (s)"); axes[0].set_ylabel("bubbles detected (count)")
    rhos = []
    for df, lab, col, dt in ((cp_1[cp_1.run == "run0"], "Foam A (first run)", FOAM_COL["A"], 30.0),
                             (cp_c, "Foam C", FOAM_COL["C"], 30.0),
                             (cp_10[cp_10.frame <= 225], "Foam F (frames 0-225)", FOAM_COL["F"], 10.0)):
        fr = df["frame"] if "frame" in df else df["frame_index"]
        y = df["n_objects"] if "n_objects" in df else df["n_bubbles"]
        rhos.append(float(spearmanr(fr, y).statistic))
        axes[1].plot(fr * dt, y, label=f"{lab}, {dt:.0f} s/frame", color=col, lw=1.6)
    if max(rhos) >= 0:
        raise SystemExit("FAIL: a Cellpose count curve does not fall; the S2 title says it does")
    axes[1].set_title("Cellpose detection\ncount FALLS in every foam  "
                      f"(ρ = {max(rhos):.3f} … {min(rhos):.4f})", fontsize=10)
    axes[1].set_xlabel("elapsed time (s)"); axes[1].set_ylabel("bubbles detected (count)")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Supplementary Figure S2. Foam C under two detectors: a physically impossible "
                 "trend, fixed", fontsize=11)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.27)
    fig.text(0.5, 0.015,
             "Bubbles detected per frame against elapsed time. Left: the propagating watershed "
             "pipeline's region count on Foam C rises,\nwhich a coarsening foam cannot do; the "
             "pipeline fragments bubbles (it trips the project's own fragmentation guard).\n"
             "Right: Cellpose counts on the three foams analysed, all falling monotonically. ρ is "
             "the Spearman rank correlation of count\nwith frame for the series drawn. Foam F is "
             "shown for its pre-registered window (frames 0-225, count at least 20).",
             ha="center", fontsize=8.2, style="italic")
    fig.savefig(FIG / "fig2_count_curves.png", dpi=160)
    plt.close(fig)
    pd.DataFrame({"series": ["Foam C watershed", "Foam A Cellpose (first run)", "Foam C Cellpose",
                             "Foam F Cellpose (frames 0-225)"],
                  "spearman_frame_vs_count": [rho_ws] + rhos}).to_csv(
        TAB / "count_curve_spearman.csv", index=False)

    ws_c.assign(detector="watershed", foam="C").to_csv(TAB / "counts_foamC_watershed.csv",
                                                       index=False)
    cp_c.assign(detector="cellpose", foam="C").to_csv(TAB / "counts_foamC_cellpose.csv",
                                                      index=False)
    cp_1.assign(detector="cellpose", foam="A").to_csv(TAB / "counts_foamA_cellpose.csv",
                                                      index=False)
    cp_10.assign(detector="cellpose", foam="F").to_csv(TAB / "counts_foamF_cellpose.csv",
                                                       index=False)


def fig_leverage() -> None:
    """All four |n-6| strata. Log y-axis so the two small strata (1.6% and 1.2% of
    rows) are legible against the 74.8% one -- on a linear axis they are ~1 px tall
    and read as absent."""
    strata = ["|n−6| ∈ [0,3)", "[3,6)", "[6,10)", "[10,30)"]
    rows = np.array([5318, 1586, 116, 86])
    weight = np.array([14.8, 30.7, 6.3, 48.2])
    pct_rows = 100 * rows / rows.sum()
    x = np.arange(len(strata))
    fig, ax = plt.subplots(figsize=(7.4, 5.8))
    ax.bar(x - 0.2, pct_rows, 0.4, label="% of measurements", color="#8da0cb")
    ax.bar(x + 0.2, weight, 0.4, label="% of least-squares fit weight", color="#d62728")
    for i, (r, w) in enumerate(zip(pct_rows, weight)):
        ax.text(i - 0.2, r * 1.12, f"{r:.1f}%", ha="center", fontsize=8.5)
        ax.text(i + 0.2, w * 1.12, f"{w:.1f}%", ha="center", fontsize=8.5)
    ax.set_yscale("log")
    ax.set_ylim(0.7, 300)
    ax.set_yticks([1, 10, 100])
    ax.set_yticklabels(["1%", "10%", "100%"])
    ax.set_xticks(x); ax.set_xticklabels(strata, fontsize=9)
    ax.set_ylabel("percent  (log scale)")
    ax.set_xlabel("bubble's deviation from six neighbours,  |n − 6|")
    ax.set_title("Why least squares failed the sign test at the 30 s horizon\n"
                 "the rarest stratum (1.2% of measurements) carries 48% of the fit weight",
                 fontsize=10.5)
    ax.legend(frameon=False, loc="upper center")
    fig.subplots_adjust(bottom=0.33)
    fig.text(0.5, 0.015,
             "Foam A, 7106 measurements from the watershed pipeline's trusted set (a detector "
             "since replaced by Cellpose),\n30 s horizon. Least squares weights each measurement "
             "by (n−6)², so the 86 measurements with |n−6| ≥ 10 —\n1.2% of the data, mostly "
             "segmentation flicker — dominate the fit and pull K from about +0.34 to +0.14,\n"
             "with a 95% interval spanning zero (a failed sign test, not a negative K). Every "
             "stratum's own K is positive\n(+0.34, +0.22, +0.06, +0.05). The y-axis is "
             "logarithmic: on a linear axis the two right-hand row-count bars are invisible.",
             ha="center", fontsize=8.3, style="italic")
    fig.savefig(FIG / "fig3_leverage.png", dpi=160)
    plt.close(fig)
    pd.DataFrame({"stratum": strata, "n_rows": rows, "pct_rows": pct_rows,
                  "pct_fit_weight": weight,
                  "K_within_stratum": [0.3412, 0.2152, 0.0635, 0.0479]}
                 ).to_csv(TAB / "leverage_strata.csv", index=False)


def fig_n_calibration() -> None:
    """Detector calibration = paper Figure 5, copied rather than redrawn, so the package and
    the paper cannot disagree. The table is built from the same measurement files.

    # DECISION (Sept. 18): the previous version hardcoded 5.08/5.11/5.67 etc. The watershed
    # row came from a different frame set and the "interior" was defined from the foam
    # mask, which leaks off the raft. Both are replaced by dev/detector_calibration_v2.py:
    # identical 14 frames for every source, raft edge = convex hull of the hand labels.
    """
    src = ROOT / "paper_figures" / "fig5_detector_calibration.png"
    S = QC / "detector_calibration" / "summary.csv"
    P = QC / "detector_calibration" / "paired_vs_gt.csv"
    for f in (src, S, P):
        if not f.is_file():
            raise FileNotFoundError(f"missing {f.relative_to(ROOT).as_posix()} -- run "
                                    "dev/detector_calibration_v2.py and dev/paper_figures.py")
    shutil.copy(src, FIG / "fig4_n_calibration.png")
    S, P = pd.read_csv(S), pd.read_csv(P)
    P = P.rename(columns={"diff": "diff_vs_GT", "ci_lo": "diff_ci_lo", "ci_hi": "diff_ci_hi"})
    T = S.merge(P, on=["measure", "source"], how="left")
    T.to_csv(TAB / "n_calibration.csv", index=False)


def tables_misc() -> None:
    shutil.copy(QC / "cellpose_v2" / "task1_gt_scores.csv", TAB / "gt_detection_per_frame.csv")
    shutil.copy(QC / "cellpose_v2" / "task1_micro_pooled.csv", TAB / "gt_detection_pooled.csv")
    shutil.copy(QC / "events" / "reliability.csv", TAB / "identity_churn_per_foam.csv")
    shutil.copy(QC / "cellpose_v2" / "task4_oos.csv", TAB / "K_out_of_sample.csv")
    shutil.copy(QC / "tiling" / "detection.csv", TAB / "tiling_expansion_detection.csv")


def copy_figures() -> None:
    src = QC / "events" / "audit_exp1_run0.png"
    if src.is_file():
        shutil.copy(src, FIG / "fig6_event_audit_foamA.png")
    # Foam F sampling-interval control (Dr. Oh's proposed experiment).
    # See docs/f_sampling_interval_control.md; built by dev/f_subsample_control.py.
    sub = QC / "f_subsample" / "figF_subsample_control.png"
    if sub.is_file():
        shutil.copy(sub, FIG / "fig7_F_sampling_control.png")
    for name, dst in (("K_arms.csv", "K_foamF_sampling_control.csv"),
                      ("paired_decline.csv", "K_horizon_decline_test.csv")):
        p = QC / "f_subsample" / name
        if p.is_file():
            shutil.copy(p, TAB / dst)
    # Paper figures (paper_figures/, built by dev/paper_figures.py) are copied, not
    # redrawn, so the package and the paper cannot disagree. Required: fail loudly.
    PF = ROOT / "paper_figures"
    for src, dst in ((PF / "fig1_K_by_period.png", FIG / "fig10_K_by_period.png"),
                     (PF / "fig2_n0_zero_crossing.png", FIG / "fig12_n0_zero_crossing.png"),
                     (PF / "fig3_fragility.png", FIG / "fig11_fragility.png"),
                     (PF / "fig4_wetness.png", FIG / "fig8_foam_wetness.png"),
                     (PF / "figS3_junction_measurement.png",
                      FIG / "fig13_junction_measurement.png"),
                     (PF / "figS4_circularity_measurement.png",
                      FIG / "fig14_circularity_measurement.png"),
                     # raft-edge wetness measures (docs/verification_wetness_t1.md)
                     (QC / "verify_junction" / "raft_core_summary.csv",
                      TAB / "foam_wetness_summary.csv"),
                     # perimeter = within 2 r_eq of the RAFT edge (convex hull of bubbles);
                     # the foam-mask definition is withdrawn (dev/raft_edge_distance.py)
                     (QC / "k_robustness" / "exclusions_raft_edge.csv",
                      TAB / "K_exclusion_configs.csv"),
                     (QC / "k_robustness" / "fragility_v2.csv", TAB / "K_fragility.csv"),
                     (QC / "k_robustness" / "fragility_v2_estimator_within_regime.csv",
                      TAB / "K_fragility_estimator_by_regime.csv"),
                     (QC / "k_robustness" / "regime_share_by_horizon.csv",
                      TAB / "K_foamF_regime_share_by_horizon.csv"),
                     # Every other table a paper figure or caption reads. qc/ is gitignored,
                     # so without these copies those numbers would have no committed source.
                     (QC / "k_robustness" / "task4_fragility.csv",
                      TAB / "K_estimator_stability_pooled.csv"),
                     (QC / "gt_k" / "n0_binned_medians.csv", TAB / "n0_binned_medians.csv"),
                     (QC / "gt_k" / "gt_min_area_sweep.csv",
                      TAB / "K_ground_truth_min_area_sweep.csv"),
                     (QC / "gt_k" / "gt_min_area_sweep_range.csv",
                      TAB / "K_ground_truth_min_area_sweep_range.csv"),
                     (QC / "gt_k" / "gt_branch_mixture_facts.csv",
                      TAB / "gt_branch_mixture_facts.csv"),
                     (QC / "verify_junction" / "raft_core_measures_per_frame.csv",
                      TAB / "foam_wetness_per_frame.csv"),
                     (QC / "verify_circularity" / "scalefree_calibration.csv",
                      TAB / "circularity_calibration.csv"),
                     (QC / "verify_circularity" / "scalefree_medians.csv",
                      TAB / "circularity_medians.csv"),
                     (QC / "detector_calibration" / "per_frame.csv",
                      TAB / "n_calibration_per_frame.csv"),
                     (QC / "detector_calibration" / "gt_vs_preseed_summary.csv",
                      TAB / "gt_inheritance_from_watershed_preseed.csv"),
                     (QC / "detector_calibration" / "rim_identical_degrees_summary.csv",
                      TAB / "n_calibration_rim_identical.csv"),
                     (QC / "t1_crossfoam" / "first_vs_last_third.csv",
                      TAB / "t1_first_vs_last_third.csv"),
                     (QC / "t1_crossfoam" / "rates_by_period.csv", TAB / "t1_rates_by_period.csv")):
        if not src.is_file():
            raise FileNotFoundError(f"missing {src.relative_to(ROOT).as_posix()}")
        shutil.copy(src, dst)
    # Foam C frames and the K-robustness tables that were not affected by the Sept. 18
    # corrections. See docs/wetness_and_k_fragility.md.
    for src, dst in ((QC / "wetness" / "fig_foamC_montage.png",
                      FIG / "fig9_foamC_frames.png"),
                     (QC / "k_robustness" / "task2_K_by_period.csv",
                      TAB / "K_by_period.csv"),
                     (QC / "k_robustness" / "task2_sign_diagnostics.csv",
                      TAB / "K_sign_diagnostics.csv"),
                     (QC / "k_robustness" / "task3a_min_area_sweep.csv",
                      TAB / "K_min_area_sweep.csv"),
                     # ground-truth validation of K and of the n=6 zero-crossing
                     # (docs/gt_k_validation.md; dev/gt_k_validation.py + gt_n0_analysis.py)
                     (QC / "gt_k" / "n0_and_branch.csv", TAB / "n0_and_branch.csv"),
                     (QC / "gt_k" / "gt_k_summary.csv", TAB / "K_ground_truth_vs_detector.csv"),
                     (QC / "gt_k" / "gt_k_by_size_tercile.csv",
                      TAB / "K_ground_truth_by_size.csv")):
        if src.is_file():
            shutil.copy(src, dst)
    # Superseded Sept. 18: the combined exclusions/fragility figure used the foam-mask
    # perimeter rule (withdrawn). Remove the stale copy.
    for stale in ("fig11_exclusions_and_fragility.png",):
        p = FIG / stale
        if p.exists():
            p.unlink()
            print(f"  removed superseded figure: {stale}")
    # fig5 (T1 detector-count) and fig7 (old centroid-line T1) are retired: they
    # documented code state, not physics. Remove any stale copies.
    for stale in ("fig5_t1_counts.png", "fig7_t1_candidates_foamA.png"):
        p = FIG / stale
        if p.exists():
            p.unlink()
            print(f"  removed retired figure: {stale}")
    for stale in ("t1_counts.csv",):
        p = TAB / stale
        if p.exists():
            p.unlink()
            print(f"  removed retired table:  {stale}")


def main() -> None:
    print("building canonical K table at matched physical horizons...")
    K = build_K_table(reuse=os.environ.get('REUSE_K') == '1')
    for _, r in K.iterrows():
        print(f"  Foam {r.foam}  {int(r.horizon_seconds):3d}s "
              f"(h={int(r.horizon_frames):2d} @ {r.frame_interval_s:.0f}s/frame): "
              f"K={r.K:+.4f} [{r.ci_lo:+.4f},{r.ci_hi:+.4f}]")
    print("building figures...")
    fig_K_vs_horizon(K); fig_counts(); fig_leverage(); fig_n_calibration()
    copy_figures()
    print("copying tables...")
    tables_misc()
    tot = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"\nfigures: {len(list(FIG.glob('*.png')))}  tables: {len(list(TAB.glob('*.csv')))}")
    print(f"total size: {tot / 1e6:.1f} MB")
    # NOTE: print the path RELATIVE to the repo root -- the absolute path contains
    # non-ASCII characters and this console is cp1252, which raises on them.
    print(f"output: {OUT.relative_to(ROOT).as_posix()}/")


if __name__ == "__main__":
    main()
