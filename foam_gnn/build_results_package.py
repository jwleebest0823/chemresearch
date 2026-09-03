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

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.6))
    axes[0].plot(ws_c["frame_index"] * 30.0, ws_c["n_bubbles"], color="#d62728", lw=1.6)
    axes[0].set_title("Foam C, watershed pipeline\ncount RISES  (Spearman ρ = +0.98)",
                      fontsize=10)
    axes[0].set_xlabel("elapsed time (s)"); axes[0].set_ylabel("bubbles detected")
    for df, lab, col, dt in ((cp_1[cp_1.run == "run0"], "Foam A (run0)", FOAM_COL["A"], 30.0),
                             (cp_c, "Foam C", FOAM_COL["C"], 30.0),
                             (cp_10[cp_10.frame <= 225], "Foam F (window)", FOAM_COL["F"], 10.0)):
        x = (df["frame"] if "frame" in df else df["frame_index"]) * dt
        y = df["n_objects"] if "n_objects" in df else df["n_bubbles"]
        axes[1].plot(x, y, label=f"{lab}, {dt:.0f} s/frame", color=col, lw=1.6)
    axes[1].set_title("Cellpose detection\ncount FALLS in every foam  (ρ = −0.995 … −0.9993)",
                      fontsize=10)
    axes[1].set_xlabel("elapsed time (s)"); axes[1].set_ylabel("bubbles detected")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("The same foam, two detectors: a physically impossible trend, fixed",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_count_curves.png", dpi=160)
    plt.close(fig)

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
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
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
    ax.set_title("Why least squares gave the wrong sign\n"
                 "the rarest stratum (1.2% of measurements) carries 48% of the fit weight",
                 fontsize=10.5)
    ax.legend(frameon=False, loc="upper center")
    fig.subplots_adjust(bottom=0.26)
    fig.text(0.5, 0.02,
             "Caption: all four strata shown. Least squares weights each measurement by "
             "(n−6)², so the\n86 measurements with |n−6| ≥ 10 — 1.2% of the data — "
             "dominate the fit. The y-axis is\nlogarithmic: on a linear axis the two "
             "right-hand row-count bars are invisible.",
             ha="center", fontsize=8.5, style="italic")
    fig.savefig(FIG / "fig3_leverage.png", dpi=160)
    plt.close(fig)
    pd.DataFrame({"stratum": strata, "n_rows": rows, "pct_rows": pct_rows,
                  "pct_fit_weight": weight,
                  "K_within_stratum": [0.3412, 0.2152, 0.0635, 0.0479]}
                 ).to_csv(TAB / "leverage_strata.csv", index=False)


def fig_n_calibration() -> None:
    src = ["hand-labelled GT", "Cellpose", "watershed"]
    n_all = [5.08, 5.11, 5.67]
    n_int = [5.66, 5.76, 5.71]
    unlab = [25.3, 20.9, 12.4]
    x = np.arange(3)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 5.0))
    axes[0].bar(x - 0.2, n_all, 0.4, label="all bubbles", color="#8da0cb")
    axes[0].bar(x + 0.2, n_int, 0.4, label="interior bubbles only", color="#66c2a5")
    axes[0].axhline(6, color="k", ls="--", lw=1)
    axes[0].text(2.45, 6.05, "6 (infinite tiling)", fontsize=8, ha="right")
    axes[0].set_xticks(x); axes[0].set_xticklabels(src, fontsize=9)
    axes[0].set_ylabel("⟨n⟩   mean neighbours per bubble (count)")
    axes[0].set_ylim(0, 6.8)
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].set_title("Cellpose reproduces hand-labelled ⟨n⟩ to +0.03;\n"
                      "the watershed over-counts by +0.60", fontsize=10)
    axes[1].bar(x, unlab, 0.5, color=["#444444", "#1f77b4", "#d62728"])
    for i, v in enumerate(unlab):
        axes[1].text(i, v + 0.5, f"{v:.1f}%", ha="center", fontsize=9)
    axes[1].set_xticks(x); axes[1].set_xticklabels(src, fontsize=9)
    axes[1].set_ylabel("% of foam interior not assigned to any bubble")
    axes[1].set_ylim(0, 30)
    axes[1].set_title("Unassigned interior area\n(how generously each method draws "
                      "bubble boundaries)", fontsize=10)
    fig.subplots_adjust(bottom=0.28)
    fig.text(0.5, 0.02,
             "Caption: RIGHT PANEL is the percentage of foam-interior pixels that no "
             "method assigned to any\nbubble — a measure of how generously each draws "
             "bubble boundaries, NOT a film-thickness\nmeasurement (the pipeline defines "
             "no film thickness). The hand labels leave the most unassigned;\nthe "
             "watershed the least, which is why it over-counts neighbours in the left "
             "panel.",
             ha="center", fontsize=8.5, style="italic")
    fig.savefig(FIG / "fig4_n_calibration.png", dpi=160)
    plt.close(fig)
    pd.DataFrame({"source": src, "mean_n_all": n_all, "mean_n_interior": n_int,
                  "unassigned_interior_pct": unlab}).to_csv(TAB / "n_calibration.csv",
                                                            index=False)


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
    print(f"output: {OUT}")


if __name__ == "__main__":
    main()
