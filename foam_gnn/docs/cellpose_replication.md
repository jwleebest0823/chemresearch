# von Neumann on a second foam — REPLICATES IN SIGN AND SHAPE, AT A DIFFERENT MAGNITUDE

Cellpose-SAM on GPU removed the detection bottleneck that had rejected Foam C. This is
the first time the project has had **two usable foams**, so it is the first time the
headline result could be tested on anything other than the foam it was derived from.

## Task 4 first, as briefed — the replication test

**Verdict: the middle option of the three pre-committed outcomes — _replicates with a
different magnitude_ — and the magnitude gap is only partly explained by D4.**

| | Foam A (watershed, `gates_v4_repairs.md`) | **Foam C (Cellpose, this work)** |
|---|---|---|
| K robust, t+1 | +0.4833 [+0.4334, +0.5332] | **+0.1776 [+0.1666, +0.1888]** |
| K robust, t+5 | +0.4967 [+0.4533, +0.5400] | **+0.1800 [+0.1699, +0.1933]** |
| K robust, t+20 | +0.5008 [+0.4433, +0.5687] | **+0.1933 [+0.1800, +0.2058]** |
| **horizon spread** | **1.04×** | **1.09×** |
| K least squares (secondary) | +0.2658 / +0.3779 / +0.5000 | +0.2184 / +0.2188 / +0.2198 |
| Theil–Sen (cross-check) | +0.4998 / +0.4934 / +0.4854 | +0.2000 / +0.1978 / +0.1944 |
| n (rows) / bubbles at t+1 | 7,106 / 120 | **29,032 / 466** |

### The three failure modes

| failure mode | Foam A | **Foam C (Cellpose)** | |
|---|---|---|---|
| **Correct sign** (CI entirely > 0) | pass, 3/3 horizons | **pass, 3/3 horizons** | ✅ |
| **Horizon-stable** | 1.04× | **1.09×** | ✅ |
| **Beats persistence out-of-sample** | 6/6 folds | **3/6 folds** | ⚠️ |

**What replicates.** The sign is positive at every horizon with CIs far from zero, on
29k samples from 466 bubbles — an independent foam, an independent detector, and a
trusted set four times larger than Foam A's. Horizon-stability replicates too: K varies
by 9% across a 20× range of horizon, against Foam A's 4%. Both estimators and the
Theil–Sen cross-check agree to within 0.02 on Foam C, which they did *not* on the
rejected foams (`exp10_replication_attempt.md` §3 flagged estimator disagreement as a
data-quality alarm). By the two structural criteria, this is a clean replication.

**What does not.** K is **2.6–2.8× smaller** than Foam A's, and the out-of-sample test
passes in only half the cells. Both need dissecting rather than reporting as a number.

### Is the magnitude gap the D4 confound?

D4 established that K carries the units of dA/dt and is therefore confounded with each
epoch's coarsening rate, so a raw-K difference across foams is expected. The brief asked
me to say whether the difference is expected on those grounds. **Partly, but not
mostly:**

| h | K raw ratio C/A | median \|dA/dt\| A / C | **normalised K** A vs C | normalised ratio |
|---|---|---|---|---|
| 1 | 0.367 | 0.667 / 0.466 | 0.725 vs **0.381** | 0.526 |
| 5 | 0.362 | 0.570 / 0.327 | 0.872 vs **0.551** | 0.632 |
| 20 | 0.386 | 0.532 / 0.282 | 0.942 vs **0.686** | 0.728 |

Normalising by each foam's own coarsening rate — the D4 prescription — closes roughly a
third of the gap (0.37 → 0.53 at t+1) and more at long horizon (0.39 → 0.73). **A real
residual difference of 1.4–1.9× survives normalisation.** So D4 explains some of it and
cannot be invoked to explain it away.

### A measurement bias that pushes the same direction, and could not be repaired

The n-diagnostics on Foam C do **not** meet this project's own standard:

| | ⟨n⟩ all regions | ⟨n_sides⟩ trusted | free-fit n₀ (physics: 6) |
|---|---|---|---|
| Foam A, watershed, post-D2 | 5.84 | **5.93** | **6.09 / 6.10 / 6.17** |
| **Foam C, Cellpose** | 5.41 | **5.61** | **4.86 / 4.97 / 5.39** |
| Foam C, watershed (guard-rejected) | — | 3.28 | 3.18 / 3.06 / 0.30 |

Against the old watershed Foam C this is a transformation — ⟨n⟩ 3.28 → 5.61 and n₀
0.30–3.18 → 4.86–5.39, both moving toward 6 together, which is exactly the required
confirmation. **But neither indicator reaches 6**, and the required standard is that
they arrive there, not merely that they move. n₀ ≈ 5 is the more diagnostic of the two,
and it says the regression puts zero growth at a pentagon.

This matters for Task 4 because **D2 — repairing exactly this under-count — raised Foam
A's K by ~40% at every horizon.** An n under-count biases K downward, and Foam C has
one. So the true Foam C K is likely above +0.18, by an amount I cannot quantify.

I checked whether the D2 mechanism could fix it, using the same pre-registered criterion
D2 used (⟨n⟩ and n₀ move to 6 together; sweep must show a plateau, not a knife edge) —
and **it cannot** (`dev/cellpose_bridge_diag.py`):

| `bridge_radius_frac` | 0.5 (shipped) | 0.75 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|
| ⟨n⟩ | 5.380 | 5.422 | 5.444 | 5.451 | 5.453 | **5.454** |

**⟨n⟩ saturates at 5.45.** A 6× increase in the bridge cap buys 0.07 neighbours and
never approaches 6, so the shipped setting is already extracting everything bridging can
extract, and no setting was changed. The cause is visible in the gap structure: Cellpose
leaves **17.7–44.1% of the foam interior unlabelled** (watershed after D2: 13.2–13.7%),
with gap half-widths whose p99 reaches 24–31 px against a median bubble radius of
11–22 px. Those are not thin films between neighbours — they are regions wide enough to
be missed bubbles or unclaimed Plateau borders, and assigning them to the nearest label
creates no new contact. **This is a genuine limitation of Cellpose instance masks on
this data — they do not tile the plane the way a watershed partition does — and it is
not repairable by the D2 fix.**

### The out-of-sample result, dissected

| h | test epoch | K(train) | MAE vN | MAE persistence | Δ [95% CI] | beats |
|---|---|---|---|---|---|---|
| 1 | early | +0.1000 | 0.6696 | 0.7275 | −0.0579 [−0.0684, −0.0485] | **YES** |
| 1 | late | +0.1832 | 0.4506 | 0.4469 | +0.0037 [−0.0468, +0.0531] | no |
| 5 | early | +0.0933 | 0.4130 | 0.4951 | −0.0821 [−0.0950, −0.0698] | **YES** |
| 5 | late | +0.1833 | 0.2856 | 0.2758 | +0.0099 [−0.0650, +0.0852] | no |
| 20 | early | +0.0596 | 0.4021→0.3377 | 0.4021 | −0.0644 [−0.0735, −0.0561] | **YES** |
| 20 | late | +0.1950 | 0.2550 | 0.2512 | +0.0038 [−0.1332, +0.1109] | no |

The split is not random: **it beats persistence in all three early-epoch folds and none
of the three late ones**, and in the late folds the CI *straddles zero* rather than
favouring persistence — it ties, it does not lose. The mechanism is visible in the K
column: training on the late epoch gives K = +0.06 to +0.10, training on the early epoch
gives +0.18 to +0.20. Late-epoch Foam C has slowed down (median |dA/dt| falls with
frame), so a K fit there under-predicts the early epoch, and against a nearly-static late
epoch persistence is already close to optimal. This is the D4 confound appearing *within*
a single foam, and it is a weaker result than Foam A's 6/6 however it is read.

**Bottom line on Task 4.** von Neumann's law replicates on an independent foam in the two
respects that are structural — correct sign at every horizon, and a horizon-stable K —
and does so on 4× more data than the original. Its magnitude does not transfer, and
about half of that gap survives the D4 normalisation that would excuse it. A measured,
unrepairable n under-count on Cellpose masks biases Foam C's K downward by an unknown
amount, which is the leading candidate for the residue. **I am not claiming the two
foams share a K.**

Gate 3 (Task 5) reaches the same conclusion by an independent route — predictive loss
rather than fitted slopes. Foam C's K applied to Foam A is the best model in the study;
Foam A's K applied to Foam C is significantly worse than predicting nothing. **The law's
form transfers across foams; its calibration does not.**

---

## Task 1 — Cellpose as a segmentation backend, and does local scoring reproduce Colab?

`src/foam_gnn/cellpose_backend.py` loads the committed `.npy` label maps as
`SegmentationResult`, so tracking → graph → trusted set → modeling run unchanged.
`foam_mask` and `dist_to_edge` still come from `compute_foam_mask` on the **raw frame**,
so `distance_to_evap_edge` is measured identically to every previous result.

**The plate-blob removal is a pipeline step, not a Colab-only hack.** Raw Cellpose tiles
the background plate (335 of 377 "objects" on Foam A f149). `restrict_to_foam_mask`
keeps objects with ≥50% of their pixels inside the foam mask — and that mask is produced
by the project's *existing, tested* `compute_foam_mask` (edge-density → Li → close →
largest CC → fill), driven by the same `BoundaryConfig` the watershed uses. It is
derived from the raw image, never from Cellpose's output, so it cannot be tuned to
flatter the detector.

Three verification checks (`dev/cellpose_verify.py`), all fail-loud:

| check | result |
|---|---|
| local `restrict_to_foam_mask(raw)` vs the committed `_clean` masks | **exact match on all 30 frames** where both variants exist |
| local GT scoring vs `foamA_scores_clean.csv` | **max \|Δ F1@0.5\| = 5e-5** over 14 frames |
| `min_overlap_frac` knife-edge sweep (0.10 → 0.90) | **completely flat**: 118/118/118…, 42/42/42…, 555/555/555… |

The third is worth a sentence: the parameter is not merely robust, it is *inert* over a
9× range, because plate blobs are ~100% outside the foam mask and bubbles ~100% inside.
This is a bimodal criterion, not a threshold on a continuum.

### One discrepancy found and resolved: macro vs micro averaging

The brief quotes pooled **0.9906 / 0.9477 / 0.9685**. Those are **macro** averages (the
mean of the 14 per-frame values). The watershed bar of **0.9030** is a **micro** average
(pooled TP/FP/FN, `segmentation_detection_accuracy.md`). Compared like with like:

| | precision | recall | **F1@0.5** | F1@0.75 | F1@0.9 |
|---|---|---|---|---|---|
| watershed, micro (the standing bar) | 0.9252 | 0.8818 | **0.9030** | — | — |
| **Cellpose zero-shot, micro** | **0.9892** | **0.9447** | **0.9664** | 0.8580 | 0.5393 |
| Cellpose zero-shot, macro (as quoted) | 0.9906 | 0.9477 | 0.9685 | — | 0.5554 |

The conclusion is unchanged — **Cellpose beats the tuned watershed on every metric at
IoU 0.5, zero-shot** — but the honest headline number against the project's own bar is
**0.9664, not 0.9685**. The IoU 0.9 column is the real caveat: **F1 0.539**, so matched
bubbles are matched *loosely*. The watershed's F1 barely moved from IoU 0.5 to 0.9
(0.899 → 0.893); Cellpose's collapses. Cellpose finds the right bubbles; the watershed
draws better boundaries. That is consistent with the n under-count above and is the same
finding twice.

## Task 2 — quality gates on Cellpose-detected Foam C

**Foam C passes the gates that rejected it.**

| gate | watershed (rejected) | **Cellpose** |
|---|---|---|
| region count trend | 574 → 1325, **rising** | **555 → 221, falling** |
| Spearman ρ(frame, count) | **+0.98** | **−0.9993** (p = 9.6e-141) |
| worst count / running-min | **2.42×** | **1.020×** |
| **fragmentation guard (1.50×, patience 3)** | **FIRES at frame 37** | **does not fire** |
| median bubble area | collapses | **384 → 1455 px², ρ = +0.9933** |
| both physical requirements (count ↓ **and** size ↑) | no | **yes** |

The guard used is `cellpose_backend.count_trend_guard`, a detector-agnostic extraction of
the *identical* criterion embedded in `propagate.segment_track_propagated`, so the
learned detector faced exactly the test that rejected Foam C and not a re-calibrated one.
A worst-case ratio of 1.020 means the count essentially never rises: this is not a
marginal pass.

The n-indicators are reported above (§ "a measurement bias") and are the one gate Foam C
does **not** fully clear.

## Task 3 — trusted sets on Cellpose detection

| | Foam A (watershed v4) | **Foam C (Cellpose)** | Foam C (watershed v2, rejected) |
|---|---|---|---|
| rows | 7,249 | **29,573** | 6,558 |
| bubbles | 120 | **466** | 300 |
| segments | 165 | **541** | 708 |
| **median segment length** | 32 frames | **53 frames** | **7 frames** |
| max segment length | 99 | **99** | 39 |
| fraction of area trusted | — | **0.981** | — |
| ⟨n_sides⟩ | 5.93 | 5.61 | 3.28 |
| median area (px²) | 3,367 | 1,074 | 832 |

The segment-length row is the clearest single statement of what changed: the same foam
went from a median trusted run of **7 frames to 53**, and 98.1% of bubble-frame area is
now inside a trusted segment. 466 trusted bubbles against Foam A's 120 is the first time
this project has had a large trusted set.

Composition (share of trusted rows, size tercile × distance-to-edge bin, d0 = nearest the
evaporation edge) is *better spread* than Foam A's, notably in the large/near-edge cell
that Foam A essentially lacks:

| | d0 | d1 | d2 | d3 | | d0 | d1 | d2 | d3 |
|---|---|---|---|---|---|---|---|---|---|
| **Foam A** small | 0.112 | 0.063 | 0.103 | 0.056 | **Foam C** small | 0.089 | 0.059 | 0.088 | 0.098 |
| medium | 0.069 | 0.091 | 0.107 | 0.065 | medium | 0.073 | 0.060 | 0.101 | 0.099 |
| large | **0.001** | 0.142 | 0.133 | 0.058 | large | **0.030** | 0.080 | 0.114 | 0.109 |

## Task 5 — Gate 3 under genuine leave-one-foam-out

The earlier "GNN wins at t+20" was invalidated because its only training data was
guard-rejected Foam C. This is its replacement: the first evaluation in this project
where a model trains on one physical foam and is tested on another.

**Result: no learned model beats the best simple baseline in ANY of the six cells.
GNN 0/6, MLP 0/6 — and each is *significantly worse* than the best baseline in 3 of 6.**

| h | test foam | persistence | global_mean | von Neumann | MLP | **GNN** |
|---|---|---|---|---|---|---|
| 1 | A | 1.7219 | 1.7637 | **1.5669** | 1.5903 | 1.7191 |
| 1 | C | **0.7206** | 0.7213 | 0.8121 | 0.7280 | 0.7223 |
| 5 | A | 0.8549 | 0.9003 | **0.6567** | 0.7002 | 0.8518 |
| 5 | C | **0.4903** | 0.5289 | 0.6294 | 0.5705 | 0.4914 |
| 20 | A | 0.6963 | 0.7485 | **0.5003** | 0.5291 | 0.6981 |
| 20 | C | **0.4005** | 0.4068 | 0.4922 | 0.4122 | 0.4014 |

Δ versus the best baseline in each cell (positive = worse; CI = cluster bootstrap):

| h | test | MLP | **GNN** |
|---|---|---|---|
| 1 | A | +0.0233 [+0.0103, +0.0360] **worse** | +0.1522 [+0.1220, +0.1859] **worse** |
| 5 | A | +0.0435 [+0.0279, +0.0596] **worse** | +0.1951 [+0.1607, +0.2353] **worse** |
| 20 | A | +0.0288 [−0.0066, +0.0622] ties | +0.1978 [+0.1615, +0.2390] **worse** |
| 1 | C | +0.0074 [−0.0138, +0.0296] ties | +0.0017 [−0.0001, +0.0037] ties |
| 5 | C | +0.0803 [+0.0444, +0.1161] **worse** | +0.0011 [−0.0007, +0.0030] ties |
| 20 | C | +0.0117 [−0.0174, +0.0418] ties | +0.0008 [−0.0013, +0.0032] ties |

**The GNN's Foam C "ties" are not a success — they are a collapse.** Its Δ against
persistence there is +0.0008 to +0.0017 with CIs of width ~0.004: the model has learned
to predict approximately zero, i.e. it has reproduced persistence. On Foam A, where
predicting zero is a poor strategy, that same behaviour makes it significantly worse than
the von Neumann baseline in all three horizons. **The GNN does not beat the MLP anywhere.
The "topology is doing the work" retraction stands, now confirmed across two foams
instead of two sessions of one.**

### The finding that is new here: nothing transfers across foams

The best baseline is **not the same on the two foams** — von Neumann on Foam A (3/3
horizons), persistence on Foam C (3/3):

* Foam C's K (+0.18) applied to **Foam A** → von Neumann is the **best** model in the
  study (MAE 0.500 vs persistence 0.696 at t+20).
* Foam A's K (+0.48) applied to **Foam C** → von Neumann is **significantly worse than
  predicting zero** (+0.092 [+0.064, +0.122] at t+20).

That asymmetry is the D4 confound at full strength. Foam A's K over-predicts Foam C's
rates by ~2.7×, and on a foam whose late epoch barely coarsens, over-prediction is worse
than no prediction; the reverse error (under-predicting a fast foam) is cheap. **So the
law's *form* transfers — Foam C's K still beats persistence on Foam A — while its
*calibration* does not.** This is the same conclusion Task 4 reached from the K values,
arrived at independently through predictive loss.

**`# DECISION` / confound, stated plainly:** the Foam A arm is watershed-derived and the
Foam C arm Cellpose-derived, because no Cellpose Foam A trusted set can exist (Task 6).
A cross-foam gap here therefore confounds foam with detector, and Task 6 measured that
detector alone moves K by ~25–30%. The alternative was not running Gate 3 at all and
leaving the invalidated t+20 claim with nothing in its place. The GNN and MLP nulls are
robust to this confound — both models fail on *both* foams, in both directions — but the
cross-foam *calibration* finding is not cleanly separable from the detector change.

## Task 6 — is K detector-dependent? A bounded probe says **yes, in magnitude**

**The full Foam A end-to-end re-run is BLOCKED, and the blocker is measured, not
assumed.** Colab produced Cellpose masks for only 14 Foam A frames — f000/001, 024/025,
049/050, 073/074, 097/098, 120/121, 148/149 — which are **7 disjoint consecutive pairs**,
not a sequence. The longest possible run is 2 frames against
`min_persist_frames = 5`, and t+5 / t+20 partners do not exist at all. Running the real
selector on the longest available run returns **0 trusted rows / 0 segments from 118
eligible bubbles** (`dev/cellpose_foama.py` §1). Lowering `min_persist_frames` to force a
result would manufacture 2-frame "segments" with no horizon structure, so it was not done.

What is possible is a like-for-like probe: on those same 7 pairs, both detectors see
**identical frames**, so an unfiltered t+1 K can be computed for each.

| detector (same 7 pairs, unfiltered) | n | ⟨n_sides⟩ | K robust | 95% CI | K/median\|dA/dt\| |
|---|---|---|---|---|---|
| watershed | 491 | 5.75 | **+0.4332** | [+0.3822, +0.4668] | 0.722 |
| **Cellpose** | 507 | **5.18** | **+0.3167** | [+0.2769, +0.3667] | 0.453 |

**The CIs do not overlap.** Same foam, same frames, same estimator, same code — swapping
the detector moves K by a factor of 0.73. These are unfiltered numbers and so are *not*
comparable to the filtered headline +0.4833; they are comparable to each other, which is
the question Task 6 asks.

Two things follow. First, **K is detector-dependent at the ~25–30% level**, which is
important on its own: a K quoted without naming the detector is under-specified. Second,
Cellpose's ⟨n_sides⟩ is **0.57 lower than the watershed's on the very same frames** —
the same under-count seen on Foam C, now measured on a foam where the watershed provides
a reference. That makes the under-count a property of Cellpose masks, confirmed on two
foams, and it is the most likely single cause of both the Task 6 gap and part of the
Task 4 magnitude gap.

## Scope limits that every Foam C claim inherits

* **Foam C detection is GT-unvalidated.** The only Foam C ground truth is exp3 f000/f001
  and it was produced by *deleting* regions from the watershed's own pre-seed, so its
  recall is 1.0 by construction and it **cannot fairly score a non-watershed detector**
  (`foamc_detection_accuracy.md`). Cellpose's Foam C accuracy is therefore unmeasured.
  What *is* measured is that its output behaves physically (Task 2) — a necessary
  condition, not a sufficient one.
* **The n under-count is unrepaired** and biases K downward by an unquantified amount.
* **Foam A's Cellpose arm does not exist** beyond 14 frames, so "same detector, both
  foams" — the cleanest possible version of this comparison — was not run.

## Reproducing

`python dev/cellpose_verify.py` (Task 1) · `python dev/cellpose_foamc.py` (Tasks 2–4) ·
`python dev/cellpose_foama.py` (Task 6) · `python dev/cellpose_bridge_diag.py` (the n
diagnostic) · `python dev/cellpose_gate3.py` (Task 5).
Artifacts in `qc/cellpose/`.

## A library defect found and fixed en route

`modeling.k_through_origin(..., "theilsen")` is O(n²) in memory — scipy materialises
every pairwise slope. Foam A's largest fit (n = 7,106) needed 400 MB and passed
unnoticed; Foam C's Cellpose trusted set (n = 29,032) needs **5.7 GB** and raised
`MemoryError`, killing the first full run. Fixed with a documented seeded subsample above
`THEILSEN_MAX_N = 8,000`, a cap deliberately set **just above Foam A's largest fit so
every previously published Foam A number is bit-identical**. Theil–Sen is a cross-check
estimator only, never primary or secondary, so the subsample costs nothing that is
reported. Five new tests pin the behaviour, including one asserting the cap exceeds
7,106.

**GT masks untouched — combined SHA-256 verified unchanged.**
