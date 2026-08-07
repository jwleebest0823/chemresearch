# Foam F (exp10, 10 s): is von Neumann's Gate-2 failure a sampling artifact?

> **⚠ Partial retraction (added after the propagation ratchet defect was found).** The
> **Task-2 trackability numbers below are RETRACTED** — they were produced by the
> defective v1 segmenter (see `docs/propagation_ratchet_defect.md`). **The Task-3 von
> Neumann conclusion stands**: it compared 10 s vs 30 s-subsampled using the *same*
> method on both arms, so the sampling contrast was internally controlled, and the
> result was a *null* (K wrong-signed at every horizon), which the ratchet does not
> manufacture. Re-running the K-fit on corrected tracks is listed as follow-up work.

Foam F was acquired at a **10 s** inter-frame interval (vs 30 s for A/C/D/E) to test
whether the Gate-2 finding — von Neumann's law `dA/dt = K(n−6)` failing (K wrong-signed
at short horizons, horizon-dependent, worse than persistence) — is *physical* or an
artifact of **temporal under-sampling** at 30 s. The controlled contrast is **10 s vs
the SAME foam subsampled to 30 s** (every 3rd frame), which isolates sampling rate from
foam-to-foam variation.

## Task 1 — registration + diagnosis
`exp10` registered as independent **Foam F** (own CV fold; `foam_gnn.dataset`). Confirmed:
503 JPG frames, 1024×1280, 3-channel with a non-physical colour cast (discarded →
grayscale, as A/C); **inter-frame interval a clean 10.0 s** (median = min = max = 10.0,
no internal gaps) over one continuous 83.7-min session (2026-07-12).

**Magnification proxy** (frame 0, default segmentation):
| foam | foam frame-fill | n bubbles | px / bubble | Plateau 3-way |
|---|---|---|---|---|
| **F** (exp10) | **0.41** | 185 | 2880 | 0.97 |
| A (exp1) ref | 0.27 | 142 | 2468 | 0.98 |

Foam F fills more of the frame than Foam A (41% vs 27%) but has comparable pixels per
bubble (~2880 vs ~2468) — moderately higher magnification, **well within the working
regime** (not the exp8 ~6% / exp9 ~50% extremes that broke earlier). It coarsens
normally (185 → 107 → 21 bubbles over early/mid/late).

**Segmentation parameter transfer:** the default `h_maxima = 4.0` + FFT grid-notch
transfer cleanly — Plateau 3-way junction fraction **0.92–0.97** across early/mid/late
(vs Foam A 0.98). **# DECISION: no re-tune needed**; Foam F uses the global defaults.
QC overlays (`qc/exp10/exp10_f{000,251,502}_overlay.png`) confirm boundaries follow real
films (one minor known artifact: the foam-boundary mask is slightly generous at the top).

## Task 3 — THE KEY EXPERIMENT: K at 10 s vs 30 s-subsampled (same foam)
Von Neumann K = through-origin slope of `dA/dt` vs `(n−6)` on Foam F's propagated
trusted bubbles; cluster-bootstrap 95% CIs (resample whole bubbles). The control is the
**same foam** subsampled to 30 s (every 3rd frame): only the sampling interval differs.

**K vs horizon Δt (px²/s per side):**
| Δt | K (10 s data) | 95% CI | pearson | K(n−6) beats persistence? | K>0? |
|---|---|---|---|---|---|
| **10 s** | **−1.74** | [−2.97, +0.30] | −0.02 | no | no |
| 30 s | −1.24 | [−2.59, +0.29] | −0.06 | no | no |
| 50 s | −1.02 | [−2.16, +0.32] | −0.09 | no | no |
| 100 s | −0.67 | [−1.67, +0.31] | −0.14 | no | no |
| 200 s | −0.34 | [−1.22, +0.42] | −0.28 | no | no |

| Δt | K (30 s-subsampled, same foam) | 95% CI | pearson | beats persist? | K>0? |
|---|---|---|---|---|---|
| **30 s** | **−1.47** | [−4.54, +0.21] | −0.08 | no | no |
| 60 s | −1.12 | [−3.64, +0.23] | −0.18 | no | no |
| 90 s | −0.87 | [−3.02, +0.24] | −0.19 | no | no |
| 150 s | −0.26 | [−1.28, +0.28] | −0.41 | no | no |

The three Gate-2 failure modes, tested explicitly at 10 s:
- **(a) Correctly signed?** **NO.** K = **−1.74** at the native 10 s horizon — still the
  *wrong* sign (von Neumann requires K>0). Finer sampling did not flip it.
- **(b) Stable across horizons?** **NO.** K drifts −1.74 → −0.34 as Δt grows 10 → 200 s
  — the same horizon dependence Gate 2 saw, and it **persists at 10 s**, so it is not a
  30 s artifact. (It is the intrinsic noise-domination of a slope fit to a near-zero-mean
  rate: the magnitude shrinks as the window averages out noise.)
- **(c) Beats persistence?** **NO,** at any horizon, either sampling.

Across the board `pearson(n−6, dA/dt) ≈ 0` and `r²(origin) ≈ 0`: **(n−6) has no
predictive relationship with the coarsening rate** — this is a substantive null (119
bubbles at 10 s is enough power to see a real correlation), not merely wide CIs.

**The controlled contrast (the scientific core):** the 10 s and 30 s-subsampled K-curves
**nearly overlap** (figure `qc/exp10/vonneumann_10s_vs_30s.png`), both negative at every
horizon. Even the cleanest isolation — the SAME 119 good 10 s trusted bubbles, but with
`dA/dt` measured over a 30 s window (the Δt=30 s row of the 10 s table, K=−1.24) — is
still negative. Neither finer sampling nor a shorter measurement window rescues K.

**Events resolvable at 10 s but not 30 s** (same 83.7-min window):
| event | 10 s | 30 s-subsampled | revealed only by 10 s |
|---|---|---|---|
| merges (coalescence) | 414 | 196 | **218 (53% missed at 30 s)** |
| T2 disappearances | 415 | 135 | **280 (67% missed at 30 s)** |

So 10 s sampling *does* resolve ~2× the coalescence and ~3× the disappearance events —
finer sampling genuinely captures more topology; it just does not make von Neumann hold.

## Task 2 — trackability (propagation), Foam F vs A / C
Stratified by size × edge-distance (`seg_temporal`). Headline + the small×near-edge cell:
| foam | trusted-area frac | reorg-birth rate | small×edge area | small×edge birth |
|---|---|---|---|---|
| A (propagated) | 0.96 | 0.003 | 0.96 | 0.006 |
| C (propagated) | 0.69 | 0.057 | 0.45 | 0.067 |
| **F — 10 s** | **0.73** | 0.089 | **0.24** | 0.287 |
| F — 30 s-subsampled | 0.26 | 0.151 | 0.18 | 0.419 |

**Within-foam sampling control (clean — only Δt differs):** 10 s vs 30 s-subsampled on the
same Foam F: trusted-area **0.26 → 0.73** (finer sampling nearly *triples* it),
small×near-edge area **0.18 → 0.24** (+34 %), small×near-edge birth **0.42 → 0.29** (−31 %).
So finer sampling **does** improve trackability, including the small near-edge stratum —
the Task-2 hypothesis holds *directionally, within foam*. But Foam F's absolute
small×near-edge trackability (0.24) stays well below Foam A's (0.96): this is an
intrinsically denser/harder foam there (cross-foam comparison is confounded by foam
identity), so sampling helps but is not the only lever.

## Task 4 — honest interpretation: **outcome (b)**
**Von Neumann's law genuinely fails in this wet, evaporating foam, and the failure is
robust to sampling rate.** At 10 s (3× finer than Gate 2's 30 s, and on a larger, less
survivorship-biased trusted set enabled by the propagation tracker), K is still
wrong-signed, still horizon-dependent, still worse than persistence, and (n−6) still has
~zero correlation with dA/dt; the 30 s-subsample of the *same foam* reproduces it and the
two K-curves overlap. This **rules out temporal under-sampling** — the most obvious
confound the Gate-2 sign-flip/horizon-dependence pattern suggested — and thereby
**strengthens the Gate-2 result**: the classical dry-foam von Neumann relation does not
describe per-bubble coarsening here, and that conclusion does not depend on the 30 s
acquisition rate. (Physically unsurprising: von Neumann is a *dry*-foam diffusion law;
this is a wet, evaporating foam.)

**Honest caveats.** (1) The K CIs include 0, so the claim is "K is *not physical* (not
significantly positive; (n−6) unpredictive)", not "K is significantly negative." (2) These
trusted tracks come from the propagation segmenter, whose per-frame correctness is **not
yet GT-validated** (labeling in progress); but the 10 s-vs-30 s *contrast* uses the same
method on both arms, so the sampling conclusion is robust to that caveat. This did **not**
revive the physics-informed modeling path (which would have been outcome (a)).

**Artifacts:** `qc/exp10/analysis_summary.json`, `vonneumann_10s_vs_30s.png`,
`prop_{coverage,birth}_F.csv`, `prop_{trusted,bft,events,diag}_s{1,3}.*`. Drivers:
`dev/exp10_{diagnose,propagate,analyze}.py`.

---

## ADDENDUM (2026-08-05) — exp10's edge distances were never interpretable
Added, not merged into the text above, so the original record stands.

The foam-mask audit (`docs/foam_mask_coverage.md`) added a clipping diagnostic: the
fraction of the image border covered by foam. **exp10 measures 23–25%**, by far the
highest of any usable foam (exp1/exp4–exp8 = 0%, exp3 = 2–8%). The foam runs off the
field of view, so `dist_to_edge` there measures distance to the **frame**, not to the
evaporation edge.

**Consequence: any exp10 conclusion resting on radial position is unsupported.** That
includes the size × edge-distance stratification quoted in §"trackability" above — the
"small × near-edge" cell for exp10 is defined by a boundary that is partly the camera's,
not the foam's. The numbers are not retracted, but they do not mean what their column
headings say.

**What this does NOT affect: the headline result.** The 10 s vs 30 s-subsampled von
Neumann comparison uses `n_sides` and `dA/dt`, neither of which depends on
`dist_to_edge`, and both arms are the same foam under the same mask. **The conclusion
that von Neumann's failure is not a sampling artifact stands unchanged.**

Separately, the Li mask fix moved exp10's `dist_to_edge` by +6 to +21 px in the mean, so
even setting the clipping aside, the stratified numbers above are stale.

---

## ADDENDUM (2026-08-07) — the K values in this document are WITHDRAWN
Re-measured on the repaired pipeline (`docs/exp10_replication_attempt.md`).

**1. K = −1.74 (10 s) and −1.47 (30 s-subsampled) were least-squares artifacts.** Both
reproduce exactly from the July trusted sets, confirming the re-implementation — but on
that *same* data the leverage-resistant estimator gives **+0.0500** and **+0.0250**, with
CIs spanning zero. A swing of 1.79 from the estimator alone. The audit
(`docs/correctness_audit.md`) benchmarked least squares as biased −0.093 with IQR 1.04 at
1.2% contamination; exp10's contamination is evidently worse.

**2. The sampling-rate conclusion is withdrawn as UNSUPPORTED.** The claim that "von
Neumann's failure is robust to sampling rate, which strengthens Gate 2" rested on those two
negative K values. With both ≈ 0 there is no failure whose robustness could be
demonstrated. This is a withdrawal, not a reversal — nothing shows von Neumann *succeeds*
at 10 s either.

**3. exp10 cannot currently be re-measured.** It fails the same physical-trend gate that
rejected Foam C: the fragmentation guard fires at frame 234 (count 48 vs running minimum
26, 1.85×), bubble density rises 3.5 → 12 per 1e5 foam px over frames 0–50 while the foam
area falls, and after f260 the median bubble area collapses ~10×. ⟨n⟩ = 4.15 and the
free-fit n₀ = 0.83–3.23 against the physical requirement of 6.

The trackability and stratification results in this document are unaffected by (1) and (2)
but inherit (3), and the earlier addendum's point about `dist_to_edge` being uninterpretable
(23–25% border clipping) still stands.
