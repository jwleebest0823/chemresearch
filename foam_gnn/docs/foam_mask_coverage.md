# The foam-boundary mask was eating foam — audit across every foam, and the fix

Your hypothesis was right. On `exp3` f000/f001 a contiguous top section of visibly normal
foam is **outside the foam mask** (case *a*), so segmentation never ran there. The cause
is not a weak edge-density map and not the largest-connected-component step: it is that
the density **threshold scales with how much of the frame the foam fills**.

Fixed by replacing the threshold rule. Foam A **improves** (GT F1 0.8958 → 0.9030), exp3
coverage goes **84.5% → 99.4%**, and the worst case across all nine experiments goes
**84.5% → 98.2%**.

Drivers: `dev/mask_audit.py`; QC overlays in `qc/mask/`.

## 1. Diagnosis — case (a), outside the mask
On `exp3` f000 the mask spans rows **127–1023** of a 1024-row frame; the foam starts at
row ~55. The contour (`qc/mask/exp3_f000_maskcontour.png`) dips inward at the top and
**scallops around a band of large bubbles** — the signature.

Three mechanisms tested, two ruled out:

* **Largest-connected-component dropping a lobe — NO.** After closing there are exactly
  two components: the foam (550,282 px) and a 304 px speck. Nothing of size was dropped.
* **`fill_holes` should have recovered it — CANNOT.** The missing band is an **open bay**,
  not an enclosed hole: within rows 60–300, 245,554 low-density px are reachable from the
  image border and only 2,524 are enclosed. Flood-filling from the border recovers nothing
  (45.2% vs 45.4%), and closing cannot bridge a wide-mouthed bay — raising
  `density_close_ksize` 41→161 moves the mask only 45.4%→47.4%.
* **The threshold itself — YES.** Vertical density profile at column 640:

  | row | 0 | 20 | 40 | 60 | 80 | 100 | 120 | 140 | 160 | 200 | 260 |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | density | 71 | 40 | 20 | 19 | 30 | 76 | 132 | 155 | 155 | 199 | 241 |

  True background sits at ~20–50, the missing band at ~107 (median), deep foam at ~227.
  The threshold `mean + 0.4·std` lands at **151.6** — above the band, cutting off real foam.

**Why the threshold is that high — the structural defect.** `mean` and `std` are taken
over the *whole image*, in which the foam is itself the high-density class. So the more of
the frame the foam fills, the higher the threshold, and **the more foam gets cut**. That
perverse feedback is why this hits Foam C (foam ~54% of frame) and not Foam A (~27%).
Large peripheral bubbles are simply where it bites first: few films, so lowest local
density.

## 2. THE AUDIT — how wide is this? (the headline)
"Visible foam" is estimated by an **independent reference** sharing no feature or
preprocessing with the production mask: local intensity standard deviation (no CLAHE, no
Sobel) + Otsu + largest component + fill holes. Verified visually on exp3 f000, where it
traces the foam rim exactly (`qc/mask/exp3_f000_ref_vs_current.png`). It is a hair
generous, so **97–100% is "full coverage"**. `exc` = mask area outside the reference.

| exp | foam | frame | OLD cov | OLD exc | **NEW cov** | NEW exc | clip |
|---|---|---|---|---|---|---|---|
| exp1 | **A** | 0 / 49 / 97 | 97.4 / 98.8 / 99.4% | 0 / 2 / 5% | **98.7 / 99.2 / 99.6%** | 1 / 3 / 6% | 0% |
| exp3 | **C** | 0 / 49 / 97 | **84.5 / 90.3 / 93.3%** | 0% | **99.4 / 99.9 / 100%** | 1 / 1 / 2% | 8 / 4 / 2% |
| exp4 | C | 0 / 49 / 97 | 95.5 / 98.4 / 97.5% | 0% | **100 / 100 / 100%** | 2% | 0% |
| exp5 | C | 0 / 49 / 97 | 99.0 / 99.4 / 99.8% | 0 / 1 / 1% | **100 / 100 / 100%** | 2 / 3 / 3% | 0% |
| exp6 | C | 0 / 49 / 97 | 100 / 100 / 100% | 3 / 4 / 5% | 100 / 100 / 100% | 4 / 4 / 5% | 0% |
| exp7 | C | 0 / 49 / 97 | 100% | **55 / 58 / 59%** | 100% | **49 / 53 / 54%** | 0% |
| exp8 | **D** | 0 / 49 / 97 | 100% | **14 / 20 / 33%** | 99.9 / 100 / 100% | **4 / 7 / 13%** | 0% |
| exp9 | **E** | 0 / 49 / 97 | 95.4 / 99.1 / 99.8% | 0 / 3 / 13% | **98.7 / 99.0 / 98.7%** | 1 / 2 / 6% | 1 / 0 / 0% |
| exp10 | **F** | 0 / 49 / 97 | **91.9 / 95.1 / 97.4%** | 0 / 1 / 3% | **98.2 / 98.4 / 98.8%** | 5 / 7 / 7% | **25 / 23 / 24%** |

**Answers to the question that matters:**

* **Foam A was NOT affected — 97.4 / 98.8 / 99.4%.** Your existing Foam A conclusions are
  not compromised by missing foam. This is the single most important line in the session.
* **Two foams lost real foam**: `exp3` (down to **84.5%**) and `exp10` (**91.9%**), plus
  marginal `exp4`/`exp9` at f000. The shortfall is always **worst at f000 and shrinks over
  time** — exactly as the mechanism predicts, since the foam fills most of the frame early
  and shrinks as it evaporates.
* **A second, opposite defect the audit turned up unprompted:** on `exp7` and `exp8` the
  mask is **55%** and **14–33% LARGER** than the visible foam, so its boundary sits out in
  background and `dist_to_edge` is *inflated* rather than truncated. Both directions
  corrupt edge-distance; only the first was in the hypothesis. The fix roughly halves
  exp8 (33%→13%) but **exp7 remains ~50% over-inclusive — an open defect, not fixed here.**
* **Worst case across all nine experiments: 84.5% → 98.2%.**

## 3. The fix
`# DECISION` (`BoundaryConfig.thresh_mode`, default `"li"`): replace
`density > mean + thresh_k·std` with **Li's minimum-cross-entropy threshold**. Li is
computed from the histogram alone, so it is **invariant to the foam's area fraction** —
precisely the defect — and has **no free parameter**. Legacy stays reachable via
`thresh_mode="mean_k_std"`.

Five rules compared over all 27 audited frames:

| | legacy | otsu | triangle | **li** | yen |
|---|---|---|---|---|---|
| MIN coverage | 84.5% | 93.3% | 97.0% | **98.2%** | 0.2% |
| MEAN coverage | 97.5% | 96.4% | 99.6% | **99.6%** | 85.0% |
| MAX excess | 59% | **4%** | 85% | 54% | 44% |
| MEAN excess | 10% | **1%** | 18% | 9% | 5% |

**Why Li and not Otsu — I shipped Otsu first and it failed.** Otsu looked best on excess,
so it was the initial choice; the matched Foam A GT A/B then showed it **regresses every
one of the 14 frames** (§4). Otsu assumes two classes of comparable variance, but this
histogram is a narrow background spike plus a very broad foam spread, so it places the cut
too high and clips the foam rim (Foam A coverage 97.4% → 93.9%). Li's cross-entropy
criterion handles the unequal variances and is the only rule that improves coverage on
*both* foams while not increasing excess over legacy.

**Robustness — the remaining parameters barely matter.** Coverage on exp3 f000 / exp1
f000 under ±20% perturbations:

| parameter | values | exp3 / exp1 coverage |
|---|---|---|
| `edge_sigma` | 12 / 15 / 18 | 99.1·98.0 / 99.4·98.7 / 99.4·98.9 |
| `density_close_ksize` | 33 / 41 / 49 | 99.4·98.7 / 99.4·98.7 / 99.4·98.7 |
| `mask_close_ksize` | 49 / 61 / 73 | 99.2·98.7 / 99.4·98.7 / 99.4·98.7 |
| `clahe_clip` | 1.6 / 2.0 / 2.4 | 99.4·98.8 / 99.4·98.7 / 99.4·98.6 |

Everything moves by **<1.5%**. This is the opposite of knife-edge.

**Fail-loud additions.** `_density_threshold` raises on an unknown `thresh_mode`, on a
constant density map, and on a non-finite threshold. Separately, `foam_mask_clipping()`
reports the fraction of the image border covered by foam, and `compute_foam_mask` emits a
`RuntimeWarning` above `clip_border_warn_frac` (0.10): when the foam runs off the field of
view, `dist_to_edge` measures distance to the *frame*, not the evaporation edge. Measured:
exp1/exp4–exp8 = 0%, exp3 2–8%, **exp10 23–25%**, **exp2 (Foam B) 100%**.

**An honest negative on a guard I tried and did not ship.** Li and Otsu both assume a
meaningful two-class split, so I tried to guard with Otsu's separability η. η is
**0.72–0.78 on exp2 (Foam B), which has no background at all** — indistinguishable from
the 0.74–0.91 of healthy frames, because film/interior contrast keeps the histogram
bimodal regardless. **η does not detect the degenerate case**, so shipping it would have
been a guard that reassures without testing anything. The border-clipping check is the one
that actually works.

## 4. Validation — the dual constraint
### (a) Foam A: no regression — it improves
Matched A/B on the **same code path**, all 14 hand-labeled frames, IoU 0.5:

| frame | GT | legacy n / F1 | otsu n / F1 | **li n / F1** |
|---|---|---|---|---|
| 0 | 124 | 122 / 0.870 | 126 / 0.848 | **116 / 0.892** |
| 1 | 122 | 120 / 0.876 | 127 / 0.843 | **113 / 0.902** |
| 49 | 84 | 79 / 0.871 | 87 / 0.807 | 77 / 0.870 |
| 50 | 80 | 77 / 0.879 | 89 / 0.793 | **76 / 0.885** |
| 97 | 63 | 63 / 0.921 | 67 / 0.892 | 63 / 0.921 |
| 98 | 63 | 63 / 0.921 | 67 / 0.892 | 63 / 0.921 |
| 148 | 46 | 43 / 0.899 | 44 / 0.889 | 44 / 0.889 |
| 149 | 43 | 42 / 0.918 | 43 / 0.907 | 42 / 0.918 |
| 24 | 99 | 92 / 0.880 | 103 / 0.812 | **90 / 0.889** |
| 25 | 98 | 95 / 0.881 | 105 / 0.818 | **93 / 0.890** |
| 73 | 70 | 69 / 0.921 | 76 / 0.863 | 69 / 0.921 |
| 74 | 70 | 70 / 0.914 | 77 / 0.857 | 70 / 0.914 |
| 120 | 52 | 50 / 0.941 | 55 / 0.897 | 50 / 0.941 |
| 121 | 52 | 50 / 0.941 | 57 / 0.881 | 50 / 0.941 |
| **POOLED** | | **P .9092 R .8827 F1 .8958** | P .8272 R .8715 **F1 .8488** | **P .9252 R .8818 F1 .9030** |

**Li: F1 0.8958 → 0.9030**, precision 0.909 → 0.925, recall flat. Better or equal on 12 of
14 frames, and −0.001/−0.010 on the two exceptions (f049, f148). Counts stay within a few
percent of your labels. **Otsu, by contrast, regresses all 14** — which is why it is not
shipped.

### (b) Foam C covers the full visible foam — proven
`qc/mask/exp3_f000_otsu_vs_current.png` shows the corrected contour following the true rim
all the way around the top. Coverage **84.5% → 99.4%** (f000) and **90.3% → 99.9%** (f049).

### `dist_to_edge` impact — Foam A immaterial, Foam C large
| exp | frame | old mean | new mean | Δ mean | Δ p95 | Δ area |
|---|---|---|---|---|---|---|
| exp1 | 0 / 49 / 97 | 109.0 / 105.3 / 99.8 | 110.0 / 105.7 / 100.0 | **+3.2 / +1.3 / +1.1** | 5.0 / 2.0 / 2.5 | +2.1 / +0.9 / +0.9% |
| exp3 | 0 / 49 / 97 | 136.1 / 135.9 / 129.9 | 153.8 / 150.3 / 145.7 | **+38.4 / +29.0 / +26.9** | 146.5 / 111.6 / 114.8 | +19.1 / +12.1 / +9.2% |
| exp10 | 0 / 49 / 97 | 135.6 / 127.8 / 119.6 | 142.4 / 129.6 / 120.7 | **+21.2 / +12.6 / +6.2** | 60.4 / 33.5 / 13.3 | +11.6 / +9.3 / +4.6% |

**Foam A shifts by only 1–3 px in the mean (p95 ≤ 5 px) — not material.** Your Foam A
analyses stand as they are; that includes the Gate 1–3 modeling and the t+20 GNN result,
whose `distance_to_evap_edge` feature moves by a couple of pixels.

**Affected and worth recomputing** (all non-Foam-A):
1. **exp3 / all Foam C** — edge distances move by 27–38 px in the mean. Any Foam C radial
   or near-edge number is stale. (Those numbers were already flagged unreliable in
   `docs/foamc_fragmentation.md` for a separate reason.)
2. **exp10** — edge distances move by 6–21 px, *and* it carries the 23–25% border-clipping
   warning, so its edge distances were never interpretable as distance-to-evaporation-edge
   in the first place. This is new information about `docs/exp10_10s_vonneumann.md`.
3. **exp8 / exp9 near-edge trackability** (`docs/exp9_diagnostic.md`) — these are the two
   foams carrying the 14–59% *over-inclusion*, so their near-edge strata were the most
   distorted of all; exp8's excess is now 33%→13%.
4. **`exports/` CSVs** — `distance_to_evap_edge` is stale for every non-exp1 session.

I have **not** re-run these; that is a deliberate pass, not a side effect of this session.

## 5. Foam C preseeds regenerated — ready to label
`exp3` f000: **554 → 574** regions; f001: **525 → 564**. The previously-empty top band now
contains **59** and **66** detected regions, and `qc/mask/exp3_f000_preseed_new.png` shows
contours reaching the top rim. **Both frames are ready for you to resume labeling.**

## 6. Integrity
* **All 19 committed human GT masks verified byte-identical** by SHA-256 before and after
  every change (`eval/exp1/f000.png = 4c9ed952…`, `eval/exp3/f000.png = 605e3fed…`,
  `train/exp1/f024.png = b8416bfc…`). Preseeds write to `groundtruth/preseed/`.
* **Fragmentation guard untouched and active** (`raise`, ratio 1.50, patience 3).
* Suite: **141 → 145 passed**, including four new regression tests: the sparse-lobe
  recovery, `thresh_mode` fail-loud, `foam_mask_clipping`, and the clipping warning.
* `manifest.csv` carries one row you added before this session (`eval/exp3/f001`,
  `inspected_not_corrected`); committed as-is.
