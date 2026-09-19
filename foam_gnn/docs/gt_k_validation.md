# Does small-bubble detection error bias K? Tested against hand-labelled truth

> **Corrections (2026-09-18, adversarial review of the paper figures).** Two statements
> below are narrowed, and left visible where they occur:
>
> 1. **"A real asymmetry of 1.24× exists in the truth"** — not established. The hand-labelled
>    branch ratio is 1.24× with 95% interval [0.95, 1.60] resampling bubbles and [0.95,
>    1.64] resampling whole frame pairs; both include 1 (no asymmetry), which fails this
>    project's own both-schemes standard (`dev/gt_n0_analysis.py`). Cellpose's 2.42×
>    [1.95, 3.13] does exclude 1 and does not overlap the hand-labelled interval, so "the
>    detector widens the gap" stands. `qc/gt_k/n0_and_branch.csv` now carries the ratio
>    intervals.
> 2. **"The sensitivity is a real property of the data" / the branch mixture "makes the
>    absence of a plateau intelligible"** — narrowed. The size dependence is present in the
>    hand labels too (relative range 0.15 [0.06, 0.31], `qc/gt_k/gt_min_area_sweep_range.csv`),
>    so it is not only detection error; but the hand-labelled sweep *does* plateau and the
>    detected sweep on the same frames does not (0.25 [0.03, 0.62]; not resolved from 0.15),
>    so the missing plateau is attributed to the detector's wider branch gap, as the verdict
>    below already says, not to the mixture. Equal pooled K does not by itself show the size
>    dependence is detector-free, and all of this is Foam A only.

**Verdict: the reported K values do NOT need revision, and the min-area sensitivity is a
real property of the data — it is present in the hand-labelled ground truth, where there
is no detection error at all.**

**But the test turned up a real, previously unquantified detector bias, and it is in the
INTERCEPT rather than in K.** On the identical bubbles, ground truth recovers the physical
anchor n₀ = 6.01 essentially exactly; Cellpose gives n₀ = 5.21. That offset is what removes
the *plateau* from the Cellpose min-area sweep — the ground-truth sweep has one.

---

## Which horizons the ground truth supports

`gt_preseed.LABEL_FRAMES` labels **consecutive pairs** by design. The seven exp1 pairs are
f000→f001, f024→f025, f049→f050, f073→f074, f097→f098, f120→f121, f148→f149. Every pair is
one frame apart and lies inside a single contiguous run, with measured spacing 29.99–30.09 s
from the filename timestamps.

**The ground truth therefore supports exactly one horizon: 30 s.** 150 s and 600 s are not
computable from 14 non-consecutive frames and are not estimated here. This is not a
limitation for the question asked — 30 s is the horizon the entire Task 2–4 battery in
`docs/wetness_and_k_fragility.md` uses.

Per pair, 27–96 bubbles are followable (425 GT and 416 Cellpose measurements in total),
which clears the project's 20-bubble power floor in every pair.

## 1. GT-derived K versus Cellpose-derived K on the identical frames

Both sides use the **shipped** `graph.build_frame_graph` with the same gap-bridged
adjacency, the same foam mask computed from the same raw frame, and the same Hungarian
IoU ≥ 0.5 temporal matching. The only thing that changes is which label map goes in.

| population | detector | K | 95% CI (bubble) | 95% CI (frame-pair block) | n | ⟨n⟩ |
|---|---|---|---|---|---|---|
| **full** | **ground truth** | **+0.3664** | [+0.3323, +0.4167] | [+0.3054, +0.4665] | 425 | 5.32 |
| **full** | Cellpose | +0.3334 | [+0.2999, +0.3997] | [+0.3001, +0.3997] | 416 | 5.26 |
| matched | ground truth | +0.3708 | [+0.3334, +0.4299] | [+0.3275, +0.4723] | 409 | 5.41 |
| matched | Cellpose | +0.3334 | [+0.3000, +0.3999] | [+0.3001, +0.3998] | 411 | 5.28 |

Paired bootstrap of the difference, resampling the same frame-pair blocks for both:

| population | ΔK = K(GT) − K(Cellpose) | 95% CI | p | verdict |
|---|---|---|---|---|
| full | +0.0330 | [−0.0390, +0.0998] | 0.510 | **not resolved** |
| matched | +0.0374 | [−0.0332, +0.1000] | 0.336 | **not resolved** |

**Ground truth is 9% higher than Cellpose and the difference is not statistically
resolved.** With 7 frame-pair blocks the test is not powerful, and that limit is stated
rather than papered over — but the point estimate is small and the direction is the one
that would make reported values *conservative*, not inflated.

**The strongest single check is an accidental one.** GT-derived K on 7 frame pairs is
**+0.3664**; the published Foam A value from the full trusted set over 198 tracked frames
is **+0.3667**. Those are different populations measured by different procedures, and they
agree to 0.0003. The headline number is independently corroborated by hand labels.

*Sensitivity:* the temporal-match threshold is not load-bearing. At IoU ≥ 0.3 / 0.5 / 0.7
the answer is K_GT = +0.3664 / +0.3664 / +0.3664 and K_Cellpose = +0.3334 / +0.3334 /
+0.3331, on 473 / 425 / 387 measurements. At 0.7 two of the seven pairs fall below the
20-bubble floor, which the guard reports rather than hides.

## 2. Missed bubbles contribute essentially nothing

This is the decisive decomposition. **FULL** includes every bubble a detector finds;
**MATCHED** keeps only bubbles *both* detectors find at both times, so missed bubbles are
excluded by construction. If missing small bubbles biased K, the two would differ.

They do not: GT moves +0.3664 → +0.3708 and Cellpose moves +0.3334 → +0.3334.

Recall on these very frames, by ground-truth size tercile:

| tercile | GT bubbles | also found by Cellpose at both times |
|---|---|---|
| small (< 1612 px²) | 142 | **88.7%** |
| medium (1612–4269 px²) | 141 | 100.0% |
| large (> 4269 px²) | 142 | 100.0% |

Cellpose misses about one in nine small bubbles and none of the rest — the expected
pattern — and removing that population from the comparison changes K by 0.004.

## 3. The size dependence is REAL — the ground truth has it too

Sweeping the minimum-area cut on the **hand-labelled bubbles with hand-labelled
adjacency**, where detection error is zero by definition:

| min area | GT K | 95% CI | n | removed |
|---|---|---|---|---|
| 0 (no cut) | +0.3664 | [+0.3323, +0.4167] | 425 | 0% |
| 200 px² | +0.3997 | [+0.3334, +0.4334] | 402 | 5% |
| 400 px² | +0.4167 | [+0.3664, +0.4334] | 376 | 12% |
| 800 px² | **+0.4222** | [+0.3664, +0.4663] | 344 | 19% |
| 1600 px² | +0.4167 | [+0.3654, +0.4663] | 285 | 33% |
| 3200 px² | +0.4084 | [+0.3333, +0.5000] | 189 | 56% |

**K rises with the size cut in the ground truth as well** — and, unlike the Cellpose sweep,
it **plateaus** at ≈ +0.42 from 400 px² onward and turns over slightly at the largest cut.

So the answer to the question as posed is the first of the three offered outcomes:
**detection error is not biasing K, and the sensitivity is a real property of the data.**
The Cellpose sweep on Foam A (+0.3667 → +0.4166) runs to the same destination as the GT
sweep (+0.3664 → ≈+0.42); it simply keeps creeping instead of settling.

## 4. What the test *did* find: a detector bias in the intercept, not in K

Fitting the free (with-intercept) line `dA/dt = slope·(n−6) + c` on the identical matched
bubbles:

| detector | slope | intercept c | **n₀** (where dA/dt = 0) |
|---|---|---|---|
| **ground truth** | +0.3942 | **−0.0027** | **6.01** |
| Cellpose | +0.5300 | **+0.4211** | **5.21** |

**The hand labels recover n₀ = 6.01 — the physical prediction — essentially exactly.**
Cellpose, on the same bubbles, puts the zero-crossing at 5.21 with a positive offset in
dA/dt of +0.42 px² s⁻¹.

That offset matters because the robust estimator forms per-point slopes `y/x`. With an
offset, `y/x = K + c/x`, which **raises the n > 6 branch and lowers the n < 6 branch**.
Measured on the identical matched bubbles:

| detector | K (n < 6) | K (n > 6) | branch ratio |
|---|---|---|---|
| **ground truth** | +0.3499 [+0.3166, +0.4222] | +0.4333 [+0.3664, +0.5332] | **1.24×** |
| Cellpose | +0.2887 [+0.2332, +0.3249] | +0.6998 [+0.5415, +0.8334] | **2.42×** |

**Cellpose roughly doubles the branch asymmetry.** ~~A real asymmetry of 1.24× exists in the
truth;~~ the detector inflates it to 2.42× *(corrected 2026-09-18: the hand-labelled 1.24× has
interval [0.95, 1.60], which includes no asymmetry — see the note at the top)*.

### Why this produces the min-area sensitivity

Bubble area and neighbour count are strongly correlated — Spearman ρ = **+0.728** in the
ground truth, and +0.624 / +0.823 / +0.624 in Foams A / C / F. In the GT frames the small
tercile contains **zero** bubbles with n > 6. So a minimum-area cut does not mainly remove
badly measured bubbles; **it shifts the population from the low-K n < 6 branch toward the
high-K n > 6 branch.** K rises because the mixture changes, and it rises further under
Cellpose because Cellpose's branch gap is twice as wide.

This is a better account than "small bubbles are measured badly", ~~and it makes the absence
of a plateau intelligible: the mixture shifts continuously with the cut, so there is no
threshold at which it stops~~ *(withdrawn 2026-09-18: the hand-labelled sweep has the same
mixture and does plateau, so the missing plateau belongs to the detector's wider gap, not to
the mixture)*.

## 5. Foam C — consistent with the mechanism, not established

Foam C cannot be tested: its only labels are deletion-only edits of the watershed's own
output (recall 1.0 by construction), so they cannot fairly score a different detector.
What can be said is whether C's behaviour *fits* the mechanism established on Foam A.

| | Foam A | **Foam C** | Foam F |
|---|---|---|---|
| median trusted bubble area | 3146 px² | **1087 px²** | 3951 px² |
| Spearman ρ(area, n) | +0.624 | **+0.823** | +0.624 |
| branch ratio K(n>6)/K(n<6) | 1.50× | **2.25×** | 7.58× |
| min-area sweep range | 14% | **50%** | 57% |

Foam C has the smallest bubbles *and* the strongest area–n coupling, so a size cut moves
its branch mixture furthest — exactly the ordering the mechanism predicts, and C is indeed
the most size-sensitive of the two dry foams. **This is consistent. It is not established**,
because Foam C has no usable ground truth and its detection accuracy is unvalidated.

## What changes, and what does not

* **No K value is revised.** Foam A, C and F keep the values in `tables/K_fits.csv`.
* **The min-area sensitivity stays reported as a real property**, with the mechanism now
  identified: it is a branch-composition effect driven by the area–n correlation, not a
  small-bubble measurement failure.
* **A new caveat is earned**: Cellpose carries a positive offset in dA/dt that displaces the
  free-fit zero-crossing from n₀ = 6.01 (truth) to 5.21, and roughly doubles the n<6 / n>6
  branch asymmetry. This does not move the robust K materially — the robust estimator is
  what protects it — but it is the reason the Cellpose size sweep never settles.
* **The 7-block limit is real.** ΔK is not resolved; this test can exclude a *large* bias,
  not a small one.

## Artifacts

`qc/gt_k/` — `gt_vs_cellpose_measurements.csv` (one row per frame-pair × detector ×
bubble), `gt_k_summary.csv`, `gt_k_by_size_tercile.csv`, `gt_k_iou_sweep.csv`,
`summary.json`. Driver: `dev/gt_k_validation.py`.
