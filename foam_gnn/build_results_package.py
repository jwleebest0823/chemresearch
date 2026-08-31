"""Build `results_package/` — a curated set for Dr. Oh to assess the results.

Figures + short tables + two short documents. No code, no logs, no mask binaries, no
caches. Every number traces to a committed artifact under `qc/`.

Run:  python build_results_package.py
"""
from __future__ import annotations

import json
import shutil
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
QC = ROOT / "qc"
OUT = ROOT / "results_package"
FIG = OUT / "figures"
TAB = OUT / "tables"
for d in (FIG, TAB):
    d.mkdir(parents=True, exist_ok=True)

FOAM_COL = {"A": "#1f77b4", "C": "#d62728", "F": "#2ca02c"}


# --------------------------------------------------------------------------- #
def fig_K_vs_horizon() -> None:
    K = pd.read_csv(QC / "cellpose_v2" / "task4_K.csv")
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for foam, g in K.groupby("foam"):
        g = g.sort_values("horizon")
        lo = g["K"] - g["ci_lo"]
        hi = g["ci_hi"] - g["K"]
        ax.errorbar(g["horizon"], g["K"], yerr=[lo, hi], marker="o", capsize=4,
                    label=f"Foam {foam}", color=FOAM_COL.get(foam), lw=1.8, ms=7)
    ax.axhline(0, color="k", lw=0.8, ls=":")
    ax.set_xscale("log"); ax.set_xticks([1, 5, 20]); ax.set_xticklabels(["t+1", "t+5", "t+20"])
    ax.set_xlabel("prediction horizon (frames)")
    ax.set_ylabel("von Neumann K   (dA/dt = K·(n−6)),  px²/s")
    ax.set_title("K is positive at every horizon in every foam\n"
                 "robust estimator, 95% cluster-bootstrap CIs", fontsize=10)
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIG / "fig1_K_vs_horizon.png", dpi=160); plt.close(fig)
    K.to_csv(TAB / "K_fits.csv", index=False)


def fig_counts() -> None:
    """The ρ = +0.98 → −0.999 reversal: watershed vs Cellpose region counts."""
    ws = json.loads((ROOT / "colab_package" / "reference_metrics.json").read_text())
    ws_c = pd.DataFrame(ws["exp3_watershed_region_count_vs_frame"]["curve"])
    cp_c = pd.read_csv(ROOT / "cellpose_out" / "exp3_counts.csv")
    cp_1 = pd.read_csv(ROOT / "cellpose_results_v2" / "cellpose_out_v2" / "exp1_counts.csv")
    cp_10 = pd.read_csv(ROOT / "cellpose_results_v2" / "cellpose_out_v2" / "exp10_counts.csv")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=False)
    axes[0].plot(ws_c["frame_index"], ws_c["n_bubbles"], color="#d62728", lw=1.6)
    axes[0].set_title("Foam C, watershed pipeline\ncount RISES  (Spearman ρ = +0.98)",
                      fontsize=10)
    axes[0].set_xlabel("frame"); axes[0].set_ylabel("regions detected")
    for df, lab, col in ((cp_1[cp_1.run == "run0"], "Foam A (run0)", FOAM_COL["A"]),
                         (cp_c, "Foam C", FOAM_COL["C"]),
                         (cp_10[cp_10.frame <= 225], "Foam F (window)", FOAM_COL["F"])):
        x = df["frame"] if "frame" in df else df["frame_index"]
        y = df["n_objects"] if "n_objects" in df else df["n_bubbles"]
        axes[1].plot(x, y, label=lab, color=col, lw=1.6)
    axes[1].set_title("Cellpose detection\ncount FALLS in every foam  (ρ = −0.995 … −0.9993)",
                      fontsize=10)
    axes[1].set_xlabel("frame"); axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("The same foam, two detectors: a physically impossible trend, fixed",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(FIG / "fig2_count_curves.png", dpi=160); plt.close(fig)

    ws_c.assign(detector="watershed", foam="C").to_csv(TAB / "counts_foamC_watershed.csv",
                                                       index=False)
    cp_c.assign(detector="cellpose", foam="C").to_csv(TAB / "counts_foamC_cellpose.csv",
                                                      index=False)
    cp_1.assign(detector="cellpose", foam="A").to_csv(TAB / "counts_foamA_cellpose.csv",
                                                      index=False)
    cp_10.assign(detector="cellpose", foam="F").to_csv(TAB / "counts_foamF_cellpose.csv",
                                                       index=False)


def fig_leverage() -> None:
    """86 of 7106 rows (1.2%) carrying 48% of the least-squares fit weight."""
    strata = ["|n−6| ∈ [0,3)", "[3,6)", "[6,10)", "[10,30)"]
    rows = np.array([5318, 1586, 116, 86])
    weight = np.array([14.8, 30.7, 6.3, 48.2])
    x = np.arange(len(strata))
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.bar(x - 0.2, 100 * rows / rows.sum(), 0.4, label="% of rows", color="#8da0cb")
    ax.bar(x + 0.2, weight, 0.4, label="% of least-squares fit weight", color="#d62728")
    for i, (r, w) in enumerate(zip(100 * rows / rows.sum(), weight)):
        ax.text(i - 0.2, r + 1, f"{r:.1f}%", ha="center", fontsize=8)
        ax.text(i + 0.2, w + 1, f"{w:.1f}%", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(strata, fontsize=9)
    ax.set_ylabel("percent")
    ax.set_title("Why least squares gave the wrong sign\n"
                 "1.2% of rows carry 48% of the fit weight (K weights each row by (n−6)²)",
                 fontsize=10)
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIG / "fig3_leverage.png", dpi=160); plt.close(fig)
    pd.DataFrame({"stratum": strata, "n_rows": rows, "pct_rows": 100 * rows / rows.sum(),
                  "pct_fit_weight": weight,
                  "K_within_stratum": [0.3412, 0.2152, 0.0635, 0.0479]}
                 ).to_csv(TAB / "leverage_strata.csv", index=False)


def fig_n_calibration() -> None:
    """GT vs Cellpose vs watershed neighbour counts — and why 6 is the wrong target."""
    src = ["hand-labelled GT", "Cellpose", "watershed"]
    n_all = [5.08, 5.11, 5.67]
    n_int = [5.66, 5.76, 5.71]
    unlab = [25.3, 20.9, 12.4]
    x = np.arange(3)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].bar(x - 0.2, n_all, 0.4, label="all bubbles", color="#8da0cb")
    axes[0].bar(x + 0.2, n_int, 0.4, label="interior bubbles only", color="#66c2a5")
    axes[0].axhline(6, color="k", ls="--", lw=1)
    axes[0].text(2.45, 6.03, "6 (infinite tiling)", fontsize=8, ha="right")
    axes[0].set_xticks(x); axes[0].set_xticklabels(src, fontsize=9)
    axes[0].set_ylabel("⟨n⟩  mean neighbours per bubble"); axes[0].set_ylim(0, 6.8)
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].set_title("Cellpose reproduces hand-labelled ⟨n⟩ to +0.03;\n"
                      "the watershed over-counts by +0.60", fontsize=10)
    axes[1].bar(x, unlab, 0.5, color=["#444444", "#1f77b4", "#d62728"])
    for i, v in enumerate(unlab):
        axes[1].text(i, v + 0.5, f"{v:.1f}%", ha="center", fontsize=9)
    axes[1].set_xticks(x); axes[1].set_xticklabels(src, fontsize=9)
    axes[1].set_ylabel("% of foam interior carrying no bubble label")
    axes[1].set_title("A quarter of foam interior is film / Plateau border —\n"
                      "the hand labels say so too", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "fig4_n_calibration.png", dpi=160); plt.close(fig)
    pd.DataFrame({"source": src, "mean_n_all": n_all, "mean_n_interior": n_int,
                  "unlabelled_interior_pct": unlab}).to_csv(TAB / "n_calibration.csv",
                                                            index=False)


def fig_t1() -> None:
    d = json.loads((QC / "t1" / "diagnose.json").read_text())
    keys = list(d[0]["t1_counts"])
    tot = [sum(o["t1_counts"][k] for o in d) for k in keys]
    labels = ["shipped\n(unbridged)", "bridged\nmb=5 (SHIPPED NOW)",
              "bridged\nmb=3", "bridged\nmb=1"]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    cols = ["#999999", "#1f77b4", "#cccccc", "#cccccc"]
    ax.bar(range(4), tot, color=cols)
    for i, v in enumerate(tot):
        ax.text(i, v + 0.7, str(v), ha="center", fontsize=10)
    ax.set_xticks(range(4)); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("T1 neighbour-swaps detected (Foam A, 198 frames)")
    ax.set_title("The T1 famine was a detector artifact\n"
                 "grey = measured but NOT shipped (threshold relaxation, unverified)",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "fig5_t1_counts.png", dpi=160); plt.close(fig)
    pd.DataFrame({"setting": keys, "T1_count_foamA": tot}).to_csv(TAB / "t1_counts.csv",
                                                                  index=False)


def tables_misc() -> None:
    shutil.copy(QC / "cellpose_v2" / "task1_gt_scores.csv", TAB / "gt_detection_per_frame.csv")
    shutil.copy(QC / "cellpose_v2" / "task1_micro_pooled.csv", TAB / "gt_detection_pooled.csv")
    shutil.copy(QC / "events" / "reliability.csv", TAB / "identity_churn_per_foam.csv")
    shutil.copy(QC / "cellpose_v2" / "task4_oos.csv", TAB / "K_out_of_sample.csv")
    shutil.copy(QC / "tiling" / "detection.csv", TAB / "tiling_expansion_detection.csv")


def copy_figures() -> None:
    """Reuse the segmentation/GT overlays already rendered under qc/."""
    for src, dst in ((QC / "events" / "audit_exp1_run0.png",
                      FIG / "fig6_event_audit_foamA.png"),
                     (QC / "t1" / "t1_candidates_exp1_run0.png",
                      FIG / "fig7_t1_candidates_foamA.png")):
        if src.is_file():
            shutil.copy(src, dst)


def main() -> None:
    print("building figures...")
    fig_K_vs_horizon(); fig_counts(); fig_leverage(); fig_n_calibration(); fig_t1()
    copy_figures()
    print("copying tables...")
    tables_misc()
    tot = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"\nfigures: {len(list(FIG.glob('*.png')))}  tables: {len(list(TAB.glob('*.csv')))}")
    print(f"total size: {tot / 1e6:.1f} MB")
    print(f"output: {OUT}")


if __name__ == "__main__":
    main()
