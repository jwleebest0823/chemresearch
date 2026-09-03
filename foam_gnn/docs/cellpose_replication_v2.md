# von Neumann across three foams, one detector — REPLICATES IN FORM, DIFFERS IN CALIBRATION

The detector confound that made the last session's cross-foam comparison uninterpretable
is gone. Every foam is now Cellpose-detected, and Foam A is measured with **both**
detectors, so the detector effect is observed directly instead of estimated from 7
frame-pairs.

## Task 4 first, as briefed — the replication test

> **UNITS CORRECTION (2026-08-27).** Horizons were originally reported in FRAMES, so
> "t+20" meant 600 s for Foams A and C but only 200 s for Foam F (10 s/frame vs 30 s).
> All values below are now at MATCHED PHYSICAL HORIZONS of 30 / 150 / 600 s. **Foams A
> and C are unchanged** (they were already at those times); **only Foam F's numbers
> move**, and its horizon spread worsens from 1.38× to 1.59×. dA/dt itself was always
> correct — it is divided by elapsed seconds from the filename timestamps, with the
> right per-foam interval — so this is a comparability fix, not a unit bug.


**Verdict: the middle of the three pre-committed outcomes — _replicates in form,
differs in calibration_. K is positive and horizon-stable on all three foams, and its
raw magnitude is genuinely foam-dependent (CIs non-overlapping). But for the two
well-measured foams the gap very nearly closes once the detector and the D4 coarsening
rate are both accounted for — at 600 s the residual is 0.98×.**

| foam | 30 s | 150 s | 600 s | horizon spread | sign | OOS beats persistence |
|---|---|---|---|---|---|---|
| **A** (exp1, 156 bubbles) | **+0.3667** [.3334,.3999] | **+0.3643** [.3334,.3933] | **+0.3583** [.3273,.3983] | **1.02×** | ✅ 3/3 | **6/6** (leave-one-session-out) |
| **C** (exp3, 466 bubbles) | **+0.1776** [.1666,.1888] | **+0.1800** [.1699,.1933] | **+0.1933** [.1800,.2058] | **1.09×** | ✅ 3/3 | 3/6 (leave-one-epoch-out) |
| **F** (exp10, 56 bubbles) | **+0.5995** [.4001,.8672] | **+0.4900** [.2367,.8045] | **+0.3764** [.1050,.8033] | **1.59×** | ✅ 3/3 | 3/6 (leave-one-epoch-out) |
| *A, watershed (previous)* | *+0.4833* | *+0.4967* | *+0.5008* | *1.04×* | *✅* | *6/6* |

*(Foam F's frame horizons are 3 / 15 / 60 at 10 s per frame; A and C are 1 / 5 / 20 at 30 s.)*

Theil–Sen agrees with the primary estimator throughout (A +0.389/+0.387/+0.372, C
+0.208/+0.200/+0.195), which it did **not** on the rejected foams — estimator
disagreement was itself the data-quality alarm there.

### (a) The detector effect, measured directly

Same foam, same frames, same code — only the detector changes:

| h | Foam A watershed | Foam A Cellpose | ratio |
|---|---|---|---|
| 1 | +0.4833 | +0.3667 | 0.759 |
| 5 | +0.4967 | +0.3643 | 0.734 |
| 20 | +0.5008 | +0.3583 | 0.715 |
| | | **mean** | **0.736** |

**Swapping the detector moves K by a factor of 0.74**, consistently across a 20× range
of horizon. Last session this was estimated at ~0.73 from 7 unfiltered frame-pairs; the
full-sequence filtered measurement lands on the same number. That estimate is now a
measurement.

Note the direction: **Cellpose *lowers* K.** That was predicted from Task 2's mechanism
(Cellpose depresses ⟨n⟩; D2 showed repairing ⟨n⟩ raises K ~40%) before the fit was run,
and it is why part of last session's "Foam A is 2.7× Foam C" was detector bias sitting
on the Foam A side.

### (b) The A-vs-C gap, decomposed

| h | raw (watershed A vs Cellpose C) | detector-matched | + D4-normalised | detector explains | D4 explains |
|---|---|---|---|---|---|
| 1 | 2.72× | 2.06× | **1.31×** | 38% | 44% |
| 5 | 2.76× | 2.02× | **1.18×** | 42% | 48% |
| 20 | 2.59× | 1.85× | **0.98×** | 46% | 55% |

**Together the two corrections account for 82–101% of the gap, and at 600 s Foam A and
Foam C have the same normalised K to within 2%.** Neither correction is invented here:
detector-matching is the whole point of the Cellpose work, and D4 (report K normalised
by the scope's median |dA/dt|, because K carries the units of dA/dt and is confounded
with each epoch's coarsening rate) is the prescription the audit already committed to.

Two honest statements, both true, and the reader should have both:

* **Raw K is genuinely foam-dependent.** A's and C's CIs do not overlap at any horizon,
  detector held constant. A foam's K is not a universal constant.
* **Normalised K is nearly foam-independent for A and C.** What the two foams share is
  *how much of their own coarsening rate the topological term explains* — 0.50/0.65/0.67
  for A against 0.38/0.55/0.69 for C.

### (c) Foam F does not fit — and is also the worst-measured foam

Foam F's raw K is the *highest* at short horizon (+0.5995 at 30 s) but its normalised K
is by far the *lowest* (0.142 vs A's 0.500), because its median |dA/dt| is 4.23 against
Foam A's 0.73 — a ~6× larger target scale (much larger, faster-coarsening bubbles).
Adding F raises the three-foam raw spread to 3.37× at 30 s and the normalised spread to
3.53×, i.e. **D4 normalisation still does not rescue the three-foam picture.**

Note this is materially less extreme than first reported. At the original frame-matched
horizons Foam F was measured at 10 s, where its median |dA/dt| is 7.60 rather than 4.23
— a shorter interval divides the same per-frame segmentation noise by a smaller number,
inflating the apparent rate scale ~3×. That deflated F's normalised K to 0.083 and pushed
the normalised spread to 6.00×. **Part of Foam F's outlier status was an artifact of
comparing it over a 3× shorter timespan.** It remains an outlier, just a milder one.

That is reported rather than smoothed over, but it should be read alongside Task 2:
Foam F has **48.2% of its foam interior unlabelled** and a free-fit n₀ of **2.68–3.31**
against the physical 6. Its ⟨n⟩ of 4.27 means its neighbour counts are wrong by roughly
two. **A foam whose n is mis-measured by ~2 cannot test a law about n**, which is the
same standard that rejected exp10 under the watershed and Foam C before it. Foam F's K
is reported for completeness and its CI is wide ([+0.40, +0.87] at 30 s, 56 bubbles); it
should not be weighted equally with A and C.

### The three failure modes

| failure mode | Foam A | Foam C | Foam F |
|---|---|---|---|
| **Correct sign** (CI > 0 at every horizon) | ✅ | ✅ | ✅ |
| **Horizon-stable** | **1.02×** | 1.09× | 1.59× |
| **Beats persistence out-of-sample** | **6/6** | 3/6 | 3/6 |

Foam A's horizon spread of **1.02× is better than the watershed's 1.04×** — horizon
stability survives the detector change intact, which is a stronger form of replication
than the K value itself managing.

**Bottom line.** von Neumann's law replicates across three independent foams in the two
structural respects — correct sign at every horizon, and a horizon-stable K — with the
detector held constant and on 4–5× more data than the original Foam A result. Its raw
calibration does not transfer. For the two foams whose neighbour counts are trustworthy,
detector-matching plus the D4 normalisation reconcile the difference almost completely.
The third foam disagrees, and is also the one whose detection is worst.

---

## Task 1 — ingest and verification

The committed backend reads the v2 tree unchanged (`build_cellpose_results(...,
cellpose_root=...)`). Local GT scoring reproduces `foamA_scores_v2.csv` to a maximum
absolute difference of **4.9e-5** across all 14 frames and all of P/R/F1.

| | precision | recall | **F1@0.5** | F1@0.75 | F1@0.9 |
|---|---|---|---|---|---|
| watershed (the standing bar) | 0.9252 | 0.8818 | 0.9030 | — | — |
| **Cellpose v2, micro-pooled** | **0.9892** | **0.9447** | **0.9664** | 0.8580 | **0.5393** |

Identical to Cellpose v1 — expected, since the 14 GT frames' masks are unchanged
between runs; only the rest of the sequence is new. All figures are **micro**-pooled,
the convention the watershed bar uses (the macro/micro mismatch corrected last session).

The F1@0.9 of 0.539 remains the standing caveat and is the same finding as the n
under-count seen from a different angle: **Cellpose finds the right bubbles but draws
looser boundaries than the watershed.**

## Task 2 — quality gates, and the finding that reframes Task 4

All three foams pass the physical gates under Cellpose:

| foam / session | counts | ρ(frame, count) | worst ratio | guard fires | median area |
|---|---|---|---|---|---|
| A run0 | 118 → 61 | −0.9989 | 1.013 | **no** | 1698 → 3030 (rises) |
| A run1 | 60 → 28 | −0.9950 | 1.000 | **no** | 3032 → 4456 (rises) |
| C | 555 → 221 | −0.9993 | 1.020 | **no** | 384 → 1455 (rises) |
| F (window) | 62 → 20 | −0.9873 | 1.250 | **no** | 2002 → 8326 (rises) |

### The n under-count is a DETECTOR property, not a Foam C property

> **RETRACTED 2026-08-14 — see `docs/tiling_gap_investigation.md`.** This section is
> correct that the ⟨n⟩ difference tracks the detector rather than the foam, but wrong
> about **which detector is right**. Measured against the 14 GT masks: GT ⟨n⟩ = 5.08
> (population) / 5.66 (interior); **Cellpose = 5.11 / 5.76, i.e. +0.03 from truth**;
> the **watershed = 5.67 / 5.71, i.e. +0.60 too high** at the population level, from
> spurious edge contacts. The GT itself leaves **25.3%** of the foam interior
> unlabelled — more than Cellpose's 20.9% — so a quarter of foam interior genuinely is
> film and Plateau border, and the watershed's 12.4% is the anomaly.
>
> Consequently **⟨n⟩ → 6 was never an attainable target on these finite rafts** (~32%
> of bubbles sit on a free perimeter with ⟨n⟩ ≈ 4), and the paragraph below beginning
> "Consequence for Task 4" has the sign of the bias backwards: Cellpose's K is the
> better-grounded number and the watershed's +0.483 is the one more likely inflated.

This was the question the brief flagged as important, and the answer is unambiguous.
Foam A run0, **same foam, same frames**, only the detector swapped:

| | ⟨n⟩ all regions | ⟨n⟩ trusted | n₀ (t+1) | unlabelled interior |
|---|---|---|---|---|
| **Foam A, watershed** | **5.84** | **5.93** | **6.09** | **12.4%** |
| **Foam A, Cellpose** | **5.03** | **5.15** | **5.56** | **22.3%** |
| Foam C, Cellpose | 5.41 | 5.61 | 4.86 | 21.6% |
| Foam F, Cellpose | **4.27** | **4.53** | **3.28** | **48.2%** |

Last session I attributed the low ⟨n⟩ to something about Foam C. **That was wrong.**
Cellpose costs ~0.5–0.8 neighbours on the foam where the watershed does best, and the
deficit tracks the unlabelled fraction across all three foams — 12.4% → 22.3% → 48.2%
maps onto ⟨n⟩ 5.84 → 5.03 → 4.27. That is a mechanism, not a correlation: Cellpose emits
*instance masks* that need not tile the plane, so neighbouring bubbles separated by a
band of label 0 fail the "two positive labels touch" adjacency test, and gap-bridging
(D2) can only reach so far.

**Consequence for Task 4, stated plainly:** every Cellpose K in this document is biased
*downward* by an unquantified amount, and the bias is *larger* for foams with more
unlabelled interior. That is precisely the ordering F > A ≈ C in unlabelled fraction,
and it is a candidate explanation for why Foam F's normalised K is the outlier. It also
means the watershed's Foam A K of +0.483 is the *less* biased of the two Foam A numbers
on this axis, even though the watershed is the worse detector by F1.

## Task 3 — Foam F's usable window

exp10 decays from 62 objects to 2 by f500; fitting K to a handful of bubbles would be
meaningless. **Window: f000–f225** (226 frames, 62 → 20 objects).

`# DECISION`, registered before any K was fitted: the window ends at the last frame with
count ≥ `StabilityConfig.min_trusted_bubbles` (= 20) — the project's *own* power gate,
not a threshold chosen by inspecting K. Sensitivity:

| min objects | 10 | 15 | **20** | 25 | 30 | 40 |
|---|---|---|---|---|---|---|
| last frame | f391 | f339 | **f225** | f196 | f184 | f112 |

The boundary moves smoothly across a 4× range of the threshold — a soft cutoff, not a
cliff. Note this window is about **statistical power, not fragmentation**: exp10's
fragmentation guard does not fire even over all 503 frames (worst ratio 1.429 < 1.50),
which is itself the headline for exp10 — the foam that was guard-rejected under the
watershed is physical under Cellpose.

## Task 5 — Gate 3, three foams, one detector: the GNN fails, and not by tying

**GNN: 0/9 cells beat the best baseline, significantly worse in 7/9. MLP: 3/9, all of
them on the least trustworthy foam. von Neumann is the best baseline in 8 of 9 cells.**

| h | test | persistence | global_mean | **von Neumann** | MLP | **GNN** |
|---|---|---|---|---|---|---|
| 1 | A | 0.9441 | 1.0872 | **0.7794** | 0.8509 | 0.9243 |
| 1 | C | **0.7206** | 0.8250 | 0.7514 | 0.8327 | 0.7263 |
| 1 | F | 11.9990 | 12.0010 | **11.9615** | *11.9437* | 12.0085 |
| 5 | A | 0.7126 | 0.8933 | **0.4819** | 0.6026 | 1.2757 |
| 5 | C | 0.4903 | 0.5511 | **0.4893** | 0.7018 | 0.4908 |
| 5 | F | 5.1576 | 5.1551 | **5.1071** | *5.0592* | 5.1537 |
| 20 | A | 0.6589 | 0.8944 | **0.4073** | 0.6408 | 1.3713 |
| 20 | C | 0.4005 | 0.5977 | **0.3560** | 0.5649 | 0.4052 |
| 20 | F | 3.8877 | 3.8807 | **3.8566** | *3.7906* | 3.9120 |

### The GNN does not "tie" — it fails in two different shapes

The brief asked for this to be said explicitly rather than dressed up as a tie, and the
prediction-scale diagnostic makes it unambiguous. `scale_ratio` is the model's median
|prediction| over the target's median |rate|; 1.0 means predicting at the right scale,
0 means predicting nothing.

| test foam | GNN scale_ratio (h=1 / 5 / 20) | what it is doing |
|---|---|---|
| **A** | 0.16 / **2.51** / **2.86** | **over-predicting by ~2.5–2.9×** — MAE 1.28 and 1.37 against von Neumann's 0.48 and 0.41 |
| **C** | 0.20 / **0.06** / 0.26 | **COLLAPSED** — reproducing persistence, not competing with it |
| **F** | **0.04** / **0.04** / **0.06** | **COLLAPSED** |

So on Foam C and Foam F the GNN's near-zero Δ against persistence is **not** a
competitive tie: it has learned to predict approximately nothing, which is what
persistence already does for free. On Foam A, where predicting nothing is a poor
strategy, it instead diverges to 2.5–2.9× the target scale and becomes the worst model
in the study. **There is no cell in which it behaves sensibly.** Combined with the
audit's finding that this same GNN reaches 98% skill on a synthetic purely-topological
task, this remains a statement about the data: Delaunay adjacency plus these edge
features carry nothing for dA/dt beyond what `n_sides` already supplies.

*(A note on the `COLLAPSED` flag in the artifacts: `persistence` is flagged in every
cell, trivially and by construction — it is defined as predicting zero. The flag is
only informative for the learned models and for `von_neumann` under a small K.)*

### The MLP's three wins are all on the foam that can least support them

The MLP beats the best baseline in 3 of 9 cells — **and all three are Foam F**, by
margins of −0.018 to −0.066 on target scales of 3.8–12.0 (i.e. 0.1–1.7%). Foam F is the
foam with 48.2% unlabelled interior, n₀ = 2.7–3.3, 56 bubbles, **and** the foam whose
`distance_to_evap_edge` is uninterpretable because of mask clipping — which is one of
the three MLP input features. A sub-1% win driven partly by a feature known to be
meaningless on that foam is not evidence that the MLP has learned physics. In its
other 6 cells the MLP is significantly worse than the best baseline.

**The physical law remains the strongest model in the study**, best baseline in 8 of 9
cells, with the one exception being Foam C at t+1 where persistence edges it.

## Task 6 — the transfer asymmetry is largely LOSS GEOMETRY, not physics

Last session found Foam A's K applied to Foam C was *worse than predicting nothing*
while Foam C's K on Foam A was the best model in the study. Detector-matched, that
specific asymmetry **weakens**: Foam A's K on Foam C now **ties** persistence at t+1/t+5
and **beats** it at t+20 — because detector-matching moved A's K from +0.483 to +0.367,
closer to C's +0.178 (ratio 2.72 → 2.06).

The general pattern, however, is confirmed and is a property of the metric:

| direction | n | mean K/K_own | mean Δ vs persistence | worse than nothing |
|---|---|---|---|---|
| **under**-predicting (K too small) | 9 | 0.51 | **−0.0955** | **0 / 9** |
| **over**-predicting (K too large) | 9 | 2.15 | −0.0173 | **3 / 9** |

**Under-predicting never once hurt**, across 9 cells spanning a 2× under-estimate; it
degrades gracefully toward persistence, which is the bounded-loss end. Over-predicting
hurt badly in 3 of 9, all of them Foam F's large K applied to Foam C (K/K_own 2.37–3.57).

So the asymmetry is **substantially an artifact of MAE geometry**, not evidence that one
foam's physics governs another's: a K that is too small shrinks predictions toward zero
(bounded by the persistence loss), while a K that is too large diverges without bound.
Any future cross-foam transfer claim should be read with this in mind — "K from foam X
beats persistence on foam Y" is a much weaker statement when X's K is smaller than Y's.

## Scope limits every claim here inherits

* **Foam C and Foam F detection are GT-unvalidated.** Foam C's only ground truth
  (exp3 f000/f001) was made by *deleting* from the watershed's own pre-seed, so its
  recall is 1.0 by construction and it cannot fairly score a non-watershed detector;
  Foam F has none at all. What is measured on those foams is that their output behaves
  physically — necessary, not sufficient.
* **Foam F's `distance_to_evap_edge` is not interpretable.** exp10 trips the foam-mask
  clipping warning (21–28% of the image border covered), so the distance transform
  measures distance to the *frame*, not to the evaporation edge. K does not use it, but
  it **is** an MLP/GNN input feature, so Foam F's Gate 3 cells inherit the caveat.
* ~~**The n under-count is unrepaired** and biases every Cellpose K downward, more so
  for foams with more unlabelled interior.~~ **RETRACTED** — GT shows Cellpose's ⟨n⟩ is
  correct to +0.03 and the watershed's is +0.60 too high
  (`docs/tiling_gap_investigation.md`). Foam F's 48.2% unlabelled is still roughly
  double the GT figure, so Foam F plausibly has genuine **under-detection** — a
  different defect, not repairable by tiling.
* Foam F rests on **56 bubbles**; its CIs are wide and its n₀ is 2.7–3.3.

## Reproducing

`dev/v2_verify_and_window.py` (Tasks 1, 3) · `dev/v2_build_trusted.py` (trusted sets +
the watershed control) · `dev/v2_gates_and_K.py` (Tasks 2, 4, 6) · `dev/v2_gate3.py`
(Task 5). Artifacts in `qc/cellpose_v2/`.

**GT masks untouched — combined SHA-256 verified unchanged.**
