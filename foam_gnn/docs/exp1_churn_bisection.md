# The exp1_run1 churn: a DEFECT, and it was mine

Bisecting the churn increase flagged last session. **Verdict: defect, introduced by my own
Li foam-mask fix (5c2a542) one session ago.** Not the ratchet fix, not the Plateau gate —
neither of those can touch the export path at all. Diagnosed, fixed, and validated below.

**The one piece of good news, established first because it bounds the damage:** the
headline results (von Neumann K, the t+20 GNN win) were computed at commit **b896803
(2026-08-03)**, one day *before* the mask fix (**5c2a542, 2026-08-04**). **They never saw
this defect.** See §5.

## 1. Bisection — two of the three candidate fixes cannot reach the export path
`dev/export_all.py` builds its data with `build_segmenter()` (the classical
`WatershedSegmenter`) and `track_sequence()`. **It never calls `propagate.py`.** By
`git show --stat`:

| commit | date | what it changed | on the export path? |
|---|---|---|---|
| 9f70dfe ratchet fix | 07-27 | `propagate.py`, `config.py` (new `PropagateConfig`) | **NO** |
| 64eb428 Plateau gate | 08-03 | `propagate.py`, `config.py` (new fields) | **NO** |
| 2d16921 | 08-03 | `propagate.py` | **NO** |
| 40242f2 fragmentation guard | 08-04 | `propagate.py`, `config.py` (new fields) | **NO** |
| **5c2a542 Li mask fix** | **08-04** | **`segmentation.py`**, `config.py` (`BoundaryConfig`) | **YES** |

`git diff 67fe6af 40242f2` over `segmentation.py, tracking.py, export_csv.py, graph.py,
stability.py` is **empty**; the only other change is `dataset.py` registering exp10, which
does not touch exp1. So across the whole Jul-09 → now span the export path has exactly
**one** active change: the foam-mask threshold.

**Correction to what I wrote last session.** I said the diff was "cumulative across three
fixes and cannot be attributed to any single one." That was wrong — I inferred it from
commit dates without checking which modules the export path actually imports. It is
attributable, and it is attributable to the fix I shipped.

### The table
The pre-fix state is reachable exactly via `thresh_mode="mean_k_std"`. That is not an
assumption: I checked out the real pre-fix commit (`git worktree` at 40242f2) and compared
foam masks, distance maps and label images on exp1 f099/f150/f197 — **all nine arrays
byte-identical** to current code in legacy mode. The regenerated legacy run then
reproduces the on-disk Jul-09 export **exactly**, which also rules out any environment
drift.

| pipeline state | run0 bubbles | run0 mean len | run0 ≥5 frames | **run1 bubbles** | **run1 mean len** | **run1 ≥5 frames** |
|---|---|---|---|---|---|---|
| on-disk export (Jul 09) | 1526 | 6.98 | 25.2% | 1421 | 4.61 | 18.6% |
| **legacy re-run** (= pre-ratchet = pre-Plateau = pre-guard) | **1526** | **6.976** | **25.23%** | **1421** | **4.611** | **18.58%** |
| + ratchet fix / + Plateau gate / + frag guard | *identical by construction — not on this code path* | | | | | |
| **+ Li mask fix (5c2a542, shipped)** | 1600 | 6.64 | 23.9% | **2114** | **3.51** | **12.6%** |
| **+ stability selector (this session)** | 1600 | 6.64 | 23.9% | **1467** | **4.51** | **18.1%** |

`reorg_births / unique_bubble`: run0 0.907 → 0.909 → 0.909; run1 0.937 → **0.958** → **0.939**.

**The fix restores run1 to legacy-quality tracking.** Against legacy, run1 is now 1467
bubbles (+3.2%), mean length 4.51 (−2.2%), tracks ≥5 frames 18.1% (−0.5 pp), churn per
bubble 0.939 vs 0.937 — i.e. within noise of the pre-fix pipeline, versus +49% / −24% /
−6.0 pp before. run0 is unchanged from the shipped Li state (1600 / 6.64 / 23.9%) because
run0 contains no cliff frames; its small residual difference from legacy is the
*legitimate* mask improvement that raises GT F1 from 0.8958 to 0.9030.

## 2. The run0/run1 asymmetry — the whole diagnosis
Per-frame effect of the mask fix along exp1 (run0 = f000–098, run1 = f099–197):

| frame | run | mask area Δ | n_bubbles Δ | border clip (new) |
|---|---|---|---|---|
| 0 / 25 / 50 / 75 / 98 | run0 | +2.1 / +1.5 / +1.0 / +1.1 / +0.8% | +3 / 0 / +1 / −2 / +2 | 0% |
| 99 / 120 / 150 | run1 | +0.7 / +0.3 / +2.2% | 0 / +1 / +1 | 0% |
| **175** | run1 | **+57.7%** | **+38** | **11%** |
| **197** | run1 | **+61.8%** | **+52** | **13%** |

Against the independent local-std reference, *excess* mask area (mask outside the visible
foam):

| frame | 98 | 130 | 150 | 165 | 170 | **175** | **180** | 190 | **197** |
|---|---|---|---|---|---|---|---|---|---|
| legacy | 5% | 7% | 7% | 10% | 11% | **12%** | 13% | 13% | **13%** |
| Li (shipped) | 6% | 8% | 10% | 12% | 17% | **76%** | **66%** | 19% | **83%** |

**run0 is unaffected because the failure only exists in late frames.** As Foam A
evaporates the foam shrinks to ~18% of the frame and leaves a **low-contrast halo**; that
halo makes the mask area a **step function of the threshold**:

| threshold scale k (thr = k × legacy) | 0.90 | 0.93 | 0.95 | **1.00** | 1.05 |
|---|---|---|---|---|---|
| exp1 f000 mask area | 27.7% | 27.4% | 27.2% | 26.7% | 26.0% |
| exp1 f098 | 24.8% | 24.5% | 24.2% | 23.7% | 23.2% |
| **exp1 f175** | 35.8% | 34.0% | **30.2%** | **20.2%** | 19.7% |
| **exp1 f197** | 41.3% | **34.1%** | 21.6% | **20.3%** | 19.8% |
| exp3 f000 | 47.4% | 47.0% | 46.4% | 45.4% | 44.7% |

Early Foam A and all of Foam C are **flat**. Late Foam A has a **cliff**, and *the cliff
moves between frames* (f175's is at k≈0.95–1.00, f197's at k≈0.93–0.95). Li sits at
k≈0.94 on every exp1 frame — a stable 0.93–0.98 ratio, so Li is not misbehaving in any
detectable way — but on late frames that is **on the cliff**. The mask therefore flips
between ~20% and ~33% of the frame from one frame to the next, the watershed carves the
newly-included background halo into ~40–50 spurious regions, and the tracker cannot match
them across frames, so it mints new ids every frame.

**That is genuine identity instability, not a benign artifact of a working fix.** It is
the third hypothesis in the brief, and the discriminating evidence is: the extra regions
are *outside the visible foam* (excess 76–83% against an independent reference), they
appear and vanish frame to frame, and they are confined to exactly the frames where the
threshold sits on a cliff. Neither of the benign explanations applies — the Plateau gate
and the ratchet fix are not even executed in this code path.

**Why my validation missed it.** The 14 GT frames span f000–f149; the cross-foam audit
sampled frames 0, 49, 97. **Every validation frame was in the flat regime.** The clipping
guard I added *did* fire on 3 frames at 10–13%, and I dismissed it in writing as
"marginally over the threshold… not a defect." It was the defect.

## 3. The fix — select the threshold by local stability, not by value
`# DECISION` (`BoundaryConfig.thresh_stability`, default `"on"`): since no scalar
threshold is safe (the cliff moves), the threshold is chosen by **local stability**. Step
the threshold up while a small upward perturbation would shrink the mask by more than
`tol`; stop on the first plateau. Frames already on a plateau are untouched, so the whole
Li coverage gain is preserved and the selector only acts where the measurement says the
choice is ill-posed.

Result (excess vs the independent reference):

| frame | legacy | Li (shipped, broken) | **Li + stability** |
|---|---|---|---|
| exp1 f000 / f050 / f098 / f150 | 0 / 2 / 5 / 7% | 1 / 3 / 6 / 10% | **1 / 3 / 6 / 10%** (identical) |
| **exp1 f175** | 12% | **76%** | **14%** |
| **exp1 f180** | 13% | **66%** | **14%** |
| **exp1 f197** | 13% | **83%** | **19%** |
| **exp3 f000** (the reason Li exists) | 84% coverage | **99% coverage** | **99% coverage** |
| **exp10 f000** | 92% coverage | **98% coverage** | **98% coverage** |

Border clipping on exp1 f175/f180 goes 11%/10% → **0%**.

**Foam A GT accuracy is bit-for-bit unchanged**, because every GT frame is on a plateau:

| | precision | recall | **pooled F1** |
|---|---|---|---|
| legacy | 0.9092 | 0.8827 | 0.8958 |
| Li (shipped) | 0.9252 | 0.8818 | **0.9030** |
| **Li + stability** | 0.9252 | 0.8818 | **0.9030** |

Per-frame counts are identical to the Li column on all 14 frames.

### Robustness, and an honest limitation
Within **±20%** on both parameters the fix holds: exp1 f175 excess 13–14%, f180 13–14%,
exp3 f000 coverage 99%, exp10 98%. The only residual is f197 at 15–20%.

**But it is not robust to −50%.** At `eps=0.015` the selector fails outright — f197 stays
at 83% excess. The mechanism is a **single-step lookahead**, so a cliff further away than
`eps × thr` reads as a *false plateau*. `eps` therefore has a floor set by the cliff
width, and I have not shown it transfers to a foam with a narrower cliff. This is a
genuine limitation of the fix, encoded in a regression test rather than hidden. It is
shippable because within the required band every setting is a large improvement and none
reverts to catastrophe — unlike the knife-edge candidates I refused in earlier sessions,
where a one-step parameter change flipped the sign of the physics.

## 4. What has to be regenerated
Only artifacts produced **after 2026-08-04** used the broken mask:
* `exports/foamA/` — regenerated last session with the defect; **must be regenerated again**.
* The Foam C preseeds regenerated last session (exp3 f000/f001) — but exp3 frames are on
  a plateau (§2 table), so those are unaffected. Verified: exp3 f000 mask identical.

## 5. Impact on the headline results — bounded, but NOT re-verified
**The von Neumann recovery and the t+20 GNN result were computed at b896803 (08-03), one
day before the mask fix (08-04). They never used the flooded mask.** Their inputs came
from the legacy-mask pipeline, which the bisection shows is the stable one on late Foam A.

So the headline results are **not corrupted**. What I have **not** done is re-run them on
the fixed pipeline — that requires rebuilding the trusted set and re-running Gates 1–3 with
cluster-bootstrap CIs and leave-one-foam-out, which did not fit in this session alongside
the bisection and the fix. **Stated plainly: the headline numbers are currently validated
only at the legacy pipeline state, and their stability across the mask fix is untested.**
That is the honest status, and it is the first thing the next session should close.

The fixed pipeline differs from legacy on Foam A late frames by design (it is *more*
accurate: GT F1 0.9030 vs 0.8958), so a re-run is expected to move the numbers somewhat;
whether the t+20 GNN win survives is exactly the open question.

**Artifacts:** `qc/bisect/{mean_k_std,li}/summary.json`, `qc/eqcheck/{old,new}.npz`.
Drivers: `dev/bisect_export.py`, `dev/mask_audit.py`.
