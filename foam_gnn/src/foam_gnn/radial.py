"""
foam_gnn.radial
===============
Radial-gradient hypothesis test on the **trusted-bubble** subset
(:mod:`foam_gnn.stability`): does coarsening depend on distance to the evaporation
edge?

What is tested (effect size + CI, never a bare p-value)
-------------------------------------------------------
* **Spearman ρ(dA/dt, distance)** over trusted segments — continuous, no binning.
* **near-edge − interior** median dA/dt difference (split at the median distance).
* **von Neumann K per radial bin**: at the frame-interval level, ``dA/dt = K(n−6)``;
  K is fit per distance bin. Does the coarsening constant rise toward the edge?

All CIs are **cluster bootstraps resampling whole bubbles** (a bubble's segments/
intervals move together) so within-bubble correlation does not inflate confidence.

Pre-registered decision rule (fixed before the run; not tuned)
--------------------------------------------------------------
"gradient detected" iff the Spearman 95% CI excludes 0 AND K varies monotonically
across occupied bins with non-overlapping CIs at the extremes; else "null". A
"null" is only reported as evidence about the physics if the design had power and
was not confounded — those are decided upstream by
:func:`foam_gnn.stability.stability_gates`. This module also emits an explicit
power note so a null is distinguishable from "underpowered".

Assumptions
-----------
* Inputs are the trusted rows + segment table from
  :func:`foam_gnn.stability.select_stable_tracks`. dA/dt in px²/s; distance in px.
* This is a WITHIN-trusted-set comparison; it does NOT estimate whole-foam
  coarsening (⟨R⟩, β) — the trusted set is survivorship-selected.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PipelineConfig

__all__ = ["RadialResult", "segment_rates", "radial_gradient_test"]


@dataclass
class RadialResult:
    n_segments: int
    n_bubbles: int
    spearman_rho: float
    spearman_ci: tuple[float, float]
    effect_near_minus_far: float
    effect_ci: tuple[float, float]
    K_by_bin: pd.DataFrame
    power_note: str
    decision: str
    meta: dict = field(default_factory=dict)


def _ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or np.ptp(x) == 0:
        return float("nan")
    return float(np.polyfit(x, y, 1)[0])


def segment_rates(trusted_rows: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """Per-segment growth rate ``dA/dt`` (OLS and robust Theil–Sen) + distance.

    Returns ``segment_id | bubble_id | dA_dt_ols | dA_dt_theilsen | dist_mid |
    n_frames``.
    """
    from scipy.stats import theilslopes

    rows: list[dict] = []
    for sid, g in trusted_rows.groupby("segment_id"):
        g = g.sort_values("frame")
        t = g["time_seconds"].to_numpy(dtype=float)
        a = g["area"].to_numpy(dtype=float)
        ts = float(theilslopes(a, t)[0]) if len(t) >= 2 and np.ptp(t) > 0 else float("nan")
        rows.append({"segment_id": int(sid), "bubble_id": int(g["bubble_id"].iloc[0]),
                     "dA_dt_ols": _ols_slope(t, a), "dA_dt_theilsen": ts,
                     "n_frames": int(len(g))})
    rr = pd.DataFrame(rows)
    return rr.merge(segments[["segment_id", "dist_mid"]], on="segment_id", how="left")


def _interval_data(trusted_rows: pd.DataFrame) -> pd.DataFrame:
    """Frame-interval rows for von Neumann: ``bubble_id | dA_dt | n_minus_6 | dist``.

    For each consecutive frame pair within a segment: ``dA_dt = ΔA/Δt``, ``n−6`` and
    distance taken at the interval start.
    """
    rows: list[dict] = []
    for _sid, g in trusted_rows.groupby("segment_id"):
        g = g.sort_values("frame")
        t = g["time_seconds"].to_numpy(dtype=float)
        a = g["area"].to_numpy(dtype=float)
        n = g["n_sides"].to_numpy(dtype=float)
        d = g["distance_to_evap_edge"].to_numpy(dtype=float)
        bid = int(g["bubble_id"].iloc[0])
        for i in range(1, len(g)):
            dt = t[i] - t[i - 1]
            if dt <= 0:
                continue
            rows.append({"bubble_id": bid, "dA_dt": (a[i] - a[i - 1]) / dt,
                         "n_minus_6": n[i - 1] - 6.0, "dist": d[i - 1]})
    return pd.DataFrame(rows, columns=["bubble_id", "dA_dt", "n_minus_6", "dist"])


def _cluster_boot_ci(bubble_of: np.ndarray, stat_fn, n_boot: int, seed: int = 0):
    """95% CI from a cluster bootstrap that resamples whole bubbles.

    ``bubble_of`` : per-row bubble id. ``stat_fn(row_index_array) -> float|nan``.
    """
    rng = np.random.default_rng(seed)
    uniq = np.unique(bubble_of)
    by_bubble = {b: np.nonzero(bubble_of == b)[0] for b in uniq}
    vals: list[float] = []
    for _ in range(n_boot):
        samp = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([by_bubble[b] for b in samp])
        v = stat_fn(idx)
        if v is not None and np.isfinite(v):
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def radial_gradient_test(
    trusted_rows: pd.DataFrame,
    segments: pd.DataFrame,
    cfg: PipelineConfig,
    *,
    rate_col: str = "dA_dt_ols",
) -> RadialResult:
    """Run the radial-gradient test on the trusted subset (see module docstring)."""
    from scipy.stats import spearmanr

    ecfg = cfg.eval
    rates = segment_rates(trusted_rows, segments)
    rates = rates[np.isfinite(rates[rate_col]) & np.isfinite(rates["dist_mid"])]
    n_seg, n_bub = len(rates), int(rates["bubble_id"].nunique()) if len(rates) else 0
    if n_seg < 3:
        return RadialResult(n_seg, n_bub, float("nan"), (float("nan"), float("nan")),
                            float("nan"), (float("nan"), float("nan")),
                            pd.DataFrame(), "n<3 segments: no test", "inconclusive",
                            {"reason": "too few segments"})

    dist = rates["dist_mid"].to_numpy(dtype=float)
    rate = rates[rate_col].to_numpy(dtype=float)
    bub = rates["bubble_id"].to_numpy()

    # ── Spearman ρ(dA/dt, distance) + cluster bootstrap CI ───────────────── #
    rho = float(spearmanr(dist, rate).correlation) if np.unique(dist).size > 1 else float("nan")
    rho_ci = _cluster_boot_ci(
        bub, lambda idx: spearmanr(dist[idx], rate[idx]).correlation
        if np.unique(dist[idx]).size > 1 else np.nan, ecfg.n_bootstrap)

    # ── near-edge − interior median effect + CI (split at median distance) ─ #
    dsplit = float(np.median(dist))

    def _effect(idx):
        near, far = rate[idx][dist[idx] <= dsplit], rate[idx][dist[idx] > dsplit]
        if len(near) == 0 or len(far) == 0:
            return np.nan
        return float(np.median(near) - np.median(far))

    effect = _effect(np.arange(n_seg))
    effect_ci = _cluster_boot_ci(bub, _effect, ecfg.n_bootstrap)

    # ── von Neumann K per radial bin (interval level) ────────────────────── #
    iv = _interval_data(trusted_rows)
    K_by_bin = _k_by_bin(iv, cfg)

    # ── power note ───────────────────────────────────────────────────────── #
    mde = 1.96 / math.sqrt(max(n_bub - 3, 1))         # Fisher-z SE of Spearman ρ
    power_note = (f"n={n_seg} segments from {n_bub} bubbles → a Spearman |ρ| below "
                  f"~{min(mde, 1.0):.2f} is indistinguishable from 0 at 95% "
                  f"(a null below this = underpowered, not evidence of no gradient).")

    # ── pre-registered decision rule ─────────────────────────────────────── #
    rho_excludes_0 = np.isfinite(rho_ci[0]) and (rho_ci[0] > 0 or rho_ci[1] < 0)
    k_monotone = _k_monotone_nonoverlap(K_by_bin)
    decision = "gradient_detected" if (rho_excludes_0 and k_monotone) else "null"

    return RadialResult(
        n_seg, n_bub, rho, rho_ci, effect, effect_ci, K_by_bin, power_note, decision,
        {"rate_col": rate_col, "distance_split_px": dsplit,
         "rho_excludes_0": bool(rho_excludes_0), "k_monotone_nonoverlap": bool(k_monotone),
         "spearman_mde_95": float(min(mde, 1.0))},
    )


def _k_by_bin(iv: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    """Fit von Neumann K = slope(dA/dt vs n−6) per distance bin, with cluster-boot CI."""
    scfg, ecfg = cfg.stability, cfg.eval
    if len(iv) == 0:
        return pd.DataFrame(columns=["bin", "dist_lo", "dist_hi", "n_intervals",
                                     "n_bubbles", "K", "K_ci_lo", "K_ci_hi"])
    dmax = float(iv["dist"].max())
    edges = np.linspace(0.0, dmax + 1e-9, ecfg.radial_bins + 1)
    b = np.clip(np.digitize(iv["dist"].to_numpy(dtype=float), edges) - 1, 0, ecfg.radial_bins - 1)
    iv = iv.assign(_bin=b)
    out: list[dict] = []
    for k, g in iv.groupby("_bin"):
        x = g["n_minus_6"].to_numpy(dtype=float)
        y = g["dA_dt"].to_numpy(dtype=float)
        bub = g["bubble_id"].to_numpy()
        n_bub = int(np.unique(bub).size)
        K = _ols_slope(x, y)
        ci = (_cluster_boot_ci(bub, lambda idx: _ols_slope(x[idx], y[idx]), ecfg.n_bootstrap)
              if n_bub >= scfg.min_bubbles_per_bin else (float("nan"), float("nan")))
        out.append({"bin": int(k), "dist_lo": float(edges[k]), "dist_hi": float(edges[k + 1]),
                    "n_intervals": int(len(g)), "n_bubbles": n_bub,
                    "K": K, "K_ci_lo": ci[0], "K_ci_hi": ci[1]})
    return pd.DataFrame(out).sort_values("bin").reset_index(drop=True)


def _k_monotone_nonoverlap(K_by_bin: pd.DataFrame) -> bool:
    """True if K is monotone across occupied, CI-resolved bins with the two
    extreme bins' CIs non-overlapping (a resolved radial trend in K)."""
    k = K_by_bin[np.isfinite(K_by_bin["K_ci_lo"]) & np.isfinite(K_by_bin["K_ci_hi"])]
    if len(k) < 2:
        return False
    k = k.sort_values("dist_lo")
    lo, hi = k.iloc[0], k.iloc[-1]
    monotone = bool((k["K"].is_monotonic_increasing or k["K"].is_monotonic_decreasing))
    non_overlap = bool(hi["K_ci_lo"] > lo["K_ci_hi"] or lo["K_ci_lo"] > hi["K_ci_hi"])
    return monotone and non_overlap
