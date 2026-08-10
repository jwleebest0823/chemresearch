"""
foam_gnn.modeling
=================
Stage-1/2 modeling primitives: the per-bubble coarsening-rate **target**, the
**trivial baselines** every learned model must clear, and the **cluster-bootstrap**
evaluation harness. Pure ``pandas``/``numpy``/``scipy`` — no torch (the GNN lives
in a separate, optional module) so this is cheap to import and unit-testable.

What this operates on
---------------------
A **trusted-frame table**: the rows of :func:`foam_gnn.stability.select_stable_tracks`
(one row per frame of a trusted segment), concatenated across sessions with these
columns added by the assembly driver::

    foam | session | seg_uid | bubble_uid | segment_id | bubble_id |
    frame | time_seconds | area | n_sides | distance_to_evap_edge | cx | cy

``seg_uid`` = ``f"{session}:{segment_id}"`` (globally unique trusted segment);
``bubble_uid`` = ``f"{session}:{bubble_id}"`` (the cluster-bootstrap resampling
unit — a bubble's rows/intervals move together).

The target (# DECISION)
-----------------------
For horizon ``h`` (frames) and a frame ``t`` inside a trusted segment whose frame
``t+h`` is also in the *same* segment (segments are gap-free, so this just means the
segment extends ``h`` frames past ``t``):

* ``target_dadt`` = ``(A[t+h] - A[t]) / (time[t+h] - time[t])``  — mean areal rate
  over the horizon, px²/s. This is the quantity models predict.
* ``target_frac`` = ``(A[t+h] - A[t]) / A[t]``  — fractional change, for the
  scale-free target-distribution report (single-step ~noise vs horizon ~signal).

Small-data discipline
---------------------
* Evaluation is leave-one-foam-out (see :func:`lofo_folds`).
* Every CI is a **cluster bootstrap resampling whole bubbles** (``bubble_uid``),
  never rows — within-bubble autocorrelation would otherwise fake significance.
* Metrics are split **quiescent vs dynamic** (``EvalConfig.dynamic_frac_thresh``)
  so a "predict no change" model is not credited for the quiescent majority.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import PipelineConfig

__all__ = [
    "TRUSTED_COLUMNS",
    "FEATURE_COLUMNS",
    "lofo_folds",
    "make_horizon_samples",
    "segment_dynamic_flags",
    "target_distribution",
    "predict_persistence",
    "predict_global_mean",
    "predict_per_bubble_linear",
    "fit_von_neumann",
    "predict_von_neumann",
    "residual_structure",
    "mae",
    "cluster_bootstrap_ci",
    "paired_delta_ci",
    "evaluate_baselines",
    "BaselineResult",
]

TRUSTED_COLUMNS = ["foam", "session", "seg_uid", "bubble_uid", "segment_id",
                   "bubble_id", "frame", "time_seconds", "area", "n_sides",
                   "distance_to_evap_edge", "cx", "cy"]

# Per-bubble features available to learned models (Stage 3). NO absolute position
# (cx, cy) — isotropy is required, so absolute-position features are deliberately
# excluded here (# DECISION). distance_to_evap_edge is the only spatial feature.
FEATURE_COLUMNS = ["area", "n_sides", "distance_to_evap_edge"]


def _require_columns(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns {missing}")


def lofo_folds(trusted: pd.DataFrame) -> list[dict]:
    """Leave-one-foam-out folds from the foams actually present.

    Returns ``[{"test_foam", "train_foams"}, ...]``. A foam's sessions never split
    across train/test (the foam is the CV unit).
    """
    foams = sorted(trusted["foam"].unique())
    if len(foams) < 2:
        raise ValueError(f"need >=2 foams for LOFO, got {foams}")
    return [{"test_foam": f, "train_foams": tuple(x for x in foams if x != f)} for f in foams]


def segment_dynamic_flags(trusted: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    """Per trusted segment: total fractional area change + dynamic/quiescent flag.

    Returns ``seg_uid | bubble_uid | foam | n_frames | frac_change | dynamic``.
    ``frac_change`` = ``|A_end - A_start| / A_start`` over the segment; ``dynamic``
    iff ``frac_change >= cfg.eval.dynamic_frac_thresh``.
    """
    _require_columns(trusted, ["seg_uid", "bubble_uid", "foam", "frame", "area"], "trusted")
    rows: list[dict] = []
    thr = cfg.eval.dynamic_frac_thresh
    for suid, g in trusted.groupby("seg_uid"):
        g = g.sort_values("frame")
        a0 = float(g["area"].iloc[0])
        a1 = float(g["area"].iloc[-1])
        frac = abs(a1 - a0) / a0 if a0 > 0 else float("nan")
        rows.append({"seg_uid": suid, "bubble_uid": g["bubble_uid"].iloc[0],
                     "foam": g["foam"].iloc[0], "n_frames": int(len(g)),
                     "frac_change": frac, "dynamic": bool(frac >= thr)})
    return pd.DataFrame(rows)


def make_horizon_samples(trusted: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Build supervised samples for one horizon (see module docstring for target).

    One row per (trusted segment, start-frame ``t``) that has a partner ``t+horizon``
    in the same segment. Columns: identity (``foam, session, seg_uid, bubble_uid,
    frame``), features at ``t`` (:data:`FEATURE_COLUMNS` + ``area_t``, ``time_t``),
    ``target_dadt``, ``target_frac``, and ``past_slope`` (causal area-vs-time slope
    over the segment frames ``<= t``; NaN when <2 past points) for the per-bubble
    linear baseline.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >=1, got {horizon}")
    _require_columns(trusted, TRUSTED_COLUMNS, "trusted")
    out: list[dict] = []
    for _suid, g in trusted.groupby("seg_uid"):
        g = g.sort_values("frame")
        frame = g["frame"].to_numpy()
        t = g["time_seconds"].to_numpy(dtype=float)
        a = g["area"].to_numpy(dtype=float)
        n = len(g)
        by_frame = {int(f): i for i, f in enumerate(frame)}
        base = g.iloc[0]
        for i in range(n):
            j = by_frame.get(int(frame[i]) + horizon)
            if j is None:
                continue
            dt = t[j] - t[i]
            if dt <= 0:
                continue
            # causal past slope over frames <= t (area vs time)
            if i >= 1 and np.ptp(t[: i + 1]) > 0:
                past_slope = float(np.polyfit(t[: i + 1], a[: i + 1], 1)[0])
            else:
                past_slope = float("nan")
            row = g.iloc[i]
            out.append({
                "foam": base["foam"], "session": base["session"],
                "seg_uid": base["seg_uid"], "bubble_uid": base["bubble_uid"],
                "frame": int(frame[i]), "horizon": int(horizon),
                "area_t": float(a[i]), "time_t": float(t[i]),
                "n_sides": float(row["n_sides"]),
                "distance_to_evap_edge": float(row["distance_to_evap_edge"]),
                "target_dadt": float((a[j] - a[i]) / dt),
                "target_frac": float((a[j] - a[i]) / a[i]) if a[i] > 0 else float("nan"),
                "past_slope": past_slope,
            })
    cols = ["foam", "session", "seg_uid", "bubble_uid", "frame", "horizon",
            "area_t", "time_t", "n_sides", "distance_to_evap_edge",
            "target_dadt", "target_frac", "past_slope"]
    return pd.DataFrame(out, columns=cols)


def target_distribution(trusted: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    """Median |fractional area change| at each horizon + the segment-level change.

    Confirms whether single-step change is near pixel noise while horizon/segment
    change is real. Returns one row per horizon plus a ``segment`` row, with
    ``n_samples``, ``median_abs_frac``, ``p90_abs_frac``, ``median_abs_dadt``.
    """
    rows: list[dict] = []
    for h in cfg.eval.rollout_horizons:
        s = make_horizon_samples(trusted, h)
        af = np.abs(s["target_frac"].to_numpy(dtype=float))
        ad = np.abs(s["target_dadt"].to_numpy(dtype=float))
        af = af[np.isfinite(af)]
        rows.append({"scope": f"h={h}", "n_samples": int(len(s)),
                     "median_abs_frac": float(np.median(af)) if len(af) else float("nan"),
                     "p90_abs_frac": float(np.percentile(af, 90)) if len(af) else float("nan"),
                     "median_abs_dadt": float(np.median(ad[np.isfinite(ad)])) if len(ad) else float("nan")})
    seg = segment_dynamic_flags(trusted, cfg)
    fc = seg["frac_change"].to_numpy(dtype=float)
    fc = fc[np.isfinite(fc)]
    rows.append({"scope": "segment", "n_samples": int(len(seg)),
                 "median_abs_frac": float(np.median(fc)) if len(fc) else float("nan"),
                 "p90_abs_frac": float(np.percentile(fc, 90)) if len(fc) else float("nan"),
                 "median_abs_dadt": float("nan")})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Baselines (all return a prediction array aligned to ``samples`` rows)
# --------------------------------------------------------------------------- #
def predict_persistence(samples: pd.DataFrame) -> np.ndarray:
    """Predict zero areal rate (area persists): dA/dt = 0."""
    return np.zeros(len(samples), dtype=float)


def predict_global_mean(samples: pd.DataFrame, train_mean_dadt: float) -> np.ndarray:
    """Predict a constant rate = the TRAIN-set mean target_dadt (fit on train foam)."""
    return np.full(len(samples), float(train_mean_dadt), dtype=float)


def predict_per_bubble_linear(samples: pd.DataFrame) -> np.ndarray:
    """Predict dA/dt = the bubble's causal past area-vs-time slope.

    Falls back to 0 (persistence) where the past slope is undefined (<2 past
    points), i.e. at a segment's first frame.
    """
    p = samples["past_slope"].to_numpy(dtype=float)
    return np.where(np.isfinite(p), p, 0.0)


# --------------------------------------------------------------------------- #
# von Neumann law:  dA/dt = K (n - 6)   (the physics anchor)
# --------------------------------------------------------------------------- #
def _weighted_median(v: np.ndarray, w: np.ndarray) -> float:
    """Weighted median of ``v`` with non-negative weights ``w``."""
    o = np.argsort(v)
    v, w = v[o], w[o]
    c = np.cumsum(w)
    if c.size == 0 or c[-1] <= 0:
        return float("nan")
    return float(v[np.searchsorted(c, 0.5 * c[-1])])


# DECISION: 8,000 points -> an 8000x8000 pairwise matrix (512 MB), which is the
# regime scipy's theilslopes already ran in for Foam A (n = 7,106). The cap sits just
# ABOVE Foam A's largest fit precisely so every previously published Foam A number is
# bit-identical; only foams whose trusted sets are larger than Foam A's (i.e. Foam C
# under Cellpose, n = 26,712) take the subsample path.
THEILSEN_MAX_N = 8_000


def k_through_origin(x: np.ndarray, y: np.ndarray, method: str = "ls",
                     min_abs_x: float = 1.0, *, seed: int = 0) -> float:
    """Through-origin slope of ``y`` on ``x`` by one of several estimators.

    ``ls``        ``sum(xy)/sum(x^2)`` — least squares; every row weighted by ``x^2``.
    ``robust``    ``median(y/x)`` over ``|x| >= min_abs_x`` — the median of the
                  per-point through-origin slopes.
    ``wrobust``   weighted median of ``y/x`` with weights ``|x|``.
    ``theilsen``  median of pairwise slopes (estimates a FREE slope; cross-check only).

    # DECISION (scalability): Theil-Sen is O(n^2) in memory — scipy materialises every
    # pairwise slope. At n = 26,712 (the Cellpose Foam C trusted set at h=1) that is
    # 3.6e8 pairs = 2.7 GiB and it raises MemoryError. Above ``THEILSEN_MAX_N`` the
    # points are therefore SUBSAMPLED with a fixed seed before the pairwise fit. This
    # is safe precisely because Theil-Sen is a **cross-check**, never the primary or
    # secondary estimator, and a median of pairwise slopes converges quickly. The cap
    # is set well above Foam A's largest fit (n = 7,106), so every previously reported
    # Foam A number is bit-identical — verified by the existing tests.

    # DECISION (D1, benchmarked in dev/estimator_bench.py against a known K=0.35):
    # with the contamination rate the audit measured (1.2% of rows being flickering
    # giants — large |n-6| with a corrupted, large-magnitude dA/dt), least squares is
    # biased by -0.093 with an inter-replicate IQR of 1.04, i.e. unusable; `robust`,
    # `wrobust` and `theilsen` are all unbiased with IQR ~0.008-0.010. On clean data
    # all four agree and LS is merely the most efficient (IQR 0.0038 vs 0.0078).
    # `robust` is the shipped primary because it is the natural robust analogue of a
    # THROUGH-ORIGIN fit (each point contributes one independent slope through the
    # origin), whereas Theil-Sen's pairwise slopes correspond to a line WITH an
    # intercept and so do not encode the physical anchor n=6 -> dA/dt=0. Rows with
    # |x| < min_abs_x carry no through-origin slope information (they contribute 0 to
    # both the LS numerator and denominator), so excluding them loses nothing.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if method == "ls":
        s = float(np.sum(x * x))
        return float(np.sum(x * y) / s) if s > 0 else float("nan")
    if method == "theilsen":
        if len(x) < 3 or np.ptp(x) == 0:
            return float("nan")
        from scipy.stats import theilslopes
        if len(x) > THEILSEN_MAX_N:      # see the DECISION note above
            j = np.random.default_rng(seed).choice(len(x), THEILSEN_MAX_N, replace=False)
            x, y = x[j], y[j]
            if np.ptp(x) == 0:
                return float("nan")
        return float(theilslopes(y, x)[0])
    m = np.abs(x) >= float(min_abs_x)
    if not m.any():
        return float("nan")
    r = y[m] / x[m]
    if method == "robust":
        return float(np.median(r))
    if method == "wrobust":
        return _weighted_median(r, np.abs(x[m]))
    raise ValueError(f"unknown estimator {method!r}; "
                     "choose from {'ls','robust','wrobust','theilsen'}")


def fit_von_neumann(
    n_sides: np.ndarray,
    dadt: np.ndarray,
    *,
    bubble_of: np.ndarray | None = None,
    n_boot: int = 0,
    seed: int = 0,
    estimator: str = "ls",
) -> dict:
    """Fit ``dA/dt = K (n-6)`` and report whether K is cleanly/physically fittable.

    The physical model is a line **through the origin** (a hexagon, n=6, neither
    grows nor shrinks), so ``K`` is the through-origin slope of ``dA/dt`` vs
    ``(n-6)``; von Neumann requires ``K > 0``. Also reports the free (with-intercept)
    OLS fit as a diagnostic — a large intercept or a free slope of different sign
    means the through-origin law is a poor description.

    Returns ``{K, K_ci, pearson_r, r2_origin, slope_free, intercept_free, n,
    n_bubbles}``. ``K_ci`` is a cluster-bootstrap 95% CI on K (resampling whole
    bubbles) when ``bubble_of`` and ``n_boot`` are given, else ``(nan, nan)``.
    ``K`` is "cleanly fittable" iff ``K_ci`` is finite, entirely > 0.
    """
    x = np.asarray(n_sides, dtype=float) - 6.0
    y = np.asarray(dadt, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if bubble_of is not None:
        bubble_of = np.asarray(bubble_of)[m]
    if len(x) < 3 or np.sum(x * x) == 0:
        return {"K": float("nan"), "K_ci": (float("nan"), float("nan")),
                "pearson_r": float("nan"), "r2_origin": float("nan"),
                "slope_free": float("nan"), "intercept_free": float("nan"),
                "n": int(len(x)), "n_bubbles": 0}

    def _k(xx, yy, meth=estimator):
        return k_through_origin(xx, yy, meth)

    K = _k(x, y)
    K_ls = k_through_origin(x, y, "ls")
    K_robust = k_through_origin(x, y, "robust")
    K_theilsen = k_through_origin(x, y, "theilsen")
    # variance explained by the through-origin model, vs predicting mean(y)
    ss_res = float(np.sum((y - K * x) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2_origin = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    pear = float(np.corrcoef(x, y)[0, 1]) if np.ptp(x) > 0 and np.ptp(y) > 0 else float("nan")
    slope_free, intercept_free = (float(v) for v in np.polyfit(x, y, 1))
    # n at which the FREE fit predicts dA/dt = 0; physics says 6 (see D2 in the audit)
    n0_free = (6.0 - intercept_free / slope_free) if abs(slope_free) > 1e-12 else float("nan")
    K_ci = (float("nan"), float("nan"))
    K_ls_ci = (float("nan"), float("nan"))
    if bubble_of is not None and n_boot > 0:
        K_ci = cluster_bootstrap_ci(lambda idx: _k(x[idx], y[idx]),
                                    bubble_of, n_boot, seed=seed)
        K_ls_ci = cluster_bootstrap_ci(lambda idx: k_through_origin(x[idx], y[idx], "ls"),
                                       bubble_of, n_boot, seed=seed)
    # scale of the target, so K can be reported normalised (D4)
    med_abs = float(np.median(np.abs(y))) if len(y) else float("nan")
    return {"K": K, "K_ci": K_ci, "estimator": estimator,
            "K_ls": K_ls, "K_ls_ci": K_ls_ci, "K_robust": K_robust,
            "K_theilsen": K_theilsen, "pearson_r": pear, "r2_origin": r2_origin,
            "slope_free": slope_free, "intercept_free": intercept_free, "n0_free": n0_free,
            "median_abs_dadt": med_abs,
            "K_normalised": (K / med_abs) if med_abs > 0 else float("nan"),
            "n": int(len(x)), "n_bubbles": int(np.unique(bubble_of).size) if bubble_of is not None else 0}


def predict_von_neumann(samples: pd.DataFrame, K: float) -> np.ndarray:
    """Predict ``dA/dt = K (n_sides - 6)`` with a fitted (train-foam) ``K``."""
    return float(K) * (samples["n_sides"].to_numpy(dtype=float) - 6.0)


def residual_structure(
    samples: pd.DataFrame,
    K: float,
    cfg: PipelineConfig,
    *,
    seed: int = 0,
) -> dict:
    """Does the von Neumann residual ``dA/dt - K(n-6)`` carry LEARNABLE structure?

    Spearman ρ (cluster-boot CI) of the residual vs distance-to-edge, vs n_sides,
    and vs area — plus the residual's variance-reduction over the raw target. If no
    correlation CI excludes 0 and the residual variance ≈ target variance, there is
    nothing for a learned model to add over the classical law.
    """
    from scipy.stats import spearmanr

    resid = samples["target_dadt"].to_numpy(dtype=float) - predict_von_neumann(samples, K)
    bub = samples["bubble_uid"].to_numpy()
    feats = {"distance_to_evap_edge": samples["distance_to_evap_edge"].to_numpy(dtype=float),
             "n_sides": samples["n_sides"].to_numpy(dtype=float),
             "area_t": samples["area_t"].to_numpy(dtype=float)}
    out: dict = {}
    for name, xv in feats.items():
        m = np.isfinite(xv) & np.isfinite(resid)
        if m.sum() < 5 or np.ptp(xv[m]) == 0:
            out[name] = {"rho": float("nan"), "ci": (float("nan"), float("nan"))}
            continue
        rho = float(spearmanr(xv[m], resid[m]).correlation)
        ci = cluster_bootstrap_ci(
            lambda idx: spearmanr(xv[idx], resid[idx]).correlation
            if np.ptp(xv[idx]) > 0 else np.nan,
            bub[m], cfg.eval.n_bootstrap, seed=seed)
        out[name] = {"rho": rho, "ci": ci, "resolved": bool(np.isfinite(ci[0]) and (ci[0] > 0 or ci[1] < 0))}
    tgt = samples["target_dadt"].to_numpy(dtype=float)
    out["resid_var_frac"] = float(np.nanvar(resid) / np.nanvar(tgt)) if np.nanvar(tgt) > 0 else float("nan")
    out["n"] = int(len(samples))
    return out


# --------------------------------------------------------------------------- #
# Metrics + cluster bootstrap
# --------------------------------------------------------------------------- #
def mae(pred: np.ndarray, target: np.ndarray) -> float:
    """Mean absolute error over finite pairs (fail loud on shape mismatch)."""
    pred = np.asarray(pred, dtype=float)
    target = np.asarray(target, dtype=float)
    if pred.shape != target.shape:
        raise ValueError(f"pred {pred.shape} != target {target.shape}")
    m = np.isfinite(pred) & np.isfinite(target)
    if not m.any():
        return float("nan")
    return float(np.mean(np.abs(pred[m] - target[m])))


def cluster_bootstrap_ci(
    metric_fn,
    bubble_of: np.ndarray,
    n_boot: int,
    *,
    seed: int = 0,
) -> tuple[float, float]:
    """95% CI resampling whole bubbles. ``metric_fn(row_idx) -> float`` (NaN ok)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(bubble_of)
    by_bubble = {b: np.nonzero(bubble_of == b)[0] for b in uniq}
    vals: list[float] = []
    for _ in range(n_boot):
        samp = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([by_bubble[b] for b in samp])
        v = metric_fn(idx)
        if v is not None and np.isfinite(v):
            vals.append(v)
    if not vals:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def paired_delta_ci(
    pred: np.ndarray,
    ref: np.ndarray,
    target: np.ndarray,
    bubble_of: np.ndarray,
    n_boot: int,
    *,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Paired cluster-bootstrap of ``MAE(pred) - MAE(ref)`` (same resampled bubbles).

    Returns ``(delta_point, ci_lo, ci_hi)``. ``pred`` BEATS ``ref`` iff the whole CI
    is < 0 (improvement outside the CI). This is the correct "beats persistence"
    test — marginal-CI overlap is only a conservative proxy.
    """
    def _delta(idx):
        return mae(pred[idx], target[idx]) - mae(ref[idx], target[idx])

    point = _delta(np.arange(len(target)))
    lo, hi = cluster_bootstrap_ci(_delta, bubble_of, n_boot, seed=seed)
    return (point, lo, hi)


@dataclass
class BaselineResult:
    horizon: int
    test_foam: str
    subset: str            # "all" | "quiescent" | "dynamic"
    method: str
    n_samples: int
    n_bubbles: int
    mae: float
    ci_lo: float
    ci_hi: float
    delta_vs_persist: float = 0.0    # MAE(method) - MAE(persistence); <0 = better
    delta_ci_lo: float = 0.0
    delta_ci_hi: float = 0.0
    beats_persist: bool = False      # True iff delta CI entirely < 0


def evaluate_baselines(
    trusted: pd.DataFrame,
    cfg: PipelineConfig,
    *,
    seed: int = 0,
) -> pd.DataFrame:
    """Full Stage-1 baseline table under leave-one-foam-out.

    For each horizon × held-out foam × subset (all/quiescent/dynamic) × method
    (persistence, global_mean, per_bubble_linear): MAE (px²/s) of the areal-rate
    prediction with a cluster-bootstrap 95% CI (resampling ``bubble_uid``).
    ``global_mean`` is fit on the *training* foams only.
    """
    seg_flags = segment_dynamic_flags(trusted, cfg).set_index("seg_uid")["dynamic"].to_dict()
    folds = lofo_folds(trusted)
    out: list[dict] = []
    for h in cfg.eval.rollout_horizons:
        samples = make_horizon_samples(trusted, h)
        if samples.empty:
            continue
        samples = samples.assign(dynamic=samples["seg_uid"].map(seg_flags).astype(bool))
        for fold in folds:
            test_foam = fold["test_foam"]
            tr = samples[samples["foam"].isin(fold["train_foams"])]
            te_all = samples[samples["foam"] == test_foam]
            if te_all.empty:
                continue
            train_mean = float(tr["target_dadt"].mean()) if len(tr) else 0.0
            for subset in ("all", "quiescent", "dynamic"):
                te = te_all if subset == "all" else te_all[te_all["dynamic"] == (subset == "dynamic")]
                if te.empty:
                    continue
                target = te["target_dadt"].to_numpy(dtype=float)
                bub = te["bubble_uid"].to_numpy()
                ref = predict_persistence(te)
                preds = {
                    "persistence": ref,
                    "global_mean": predict_global_mean(te, train_mean),
                    "per_bubble_linear": predict_per_bubble_linear(te),
                }
                for method, pred in preds.items():
                    point = mae(pred, target)
                    ci = cluster_bootstrap_ci(
                        lambda idx, p=pred: mae(p[idx], target[idx]),
                        bub, cfg.eval.n_bootstrap, seed=seed)
                    if method == "persistence":
                        d_pt, d_lo, d_hi = 0.0, 0.0, 0.0
                    else:
                        d_pt, d_lo, d_hi = paired_delta_ci(
                            pred, ref, target, bub, cfg.eval.n_bootstrap, seed=seed)
                    out.append(vars(BaselineResult(
                        h, test_foam, subset, method, int(len(te)),
                        int(pd.Series(bub).nunique()), point, ci[0], ci[1],
                        d_pt, d_lo, d_hi, bool(method != "persistence" and d_hi < 0))))
    return pd.DataFrame(out)
