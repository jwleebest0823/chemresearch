# Is Foam C labelable now? — verdict: **only the early frames**

Tests the hypothesis that Foam C's ~1189-region preseed was mostly Plateau-border
artifacts, and that rejecting them makes the frame correctable by hand.

**Answer: partly.** The early frames drop by half and look clean; **the mid and late
frames do not, and are demonstrably fragmenting.** Recommendation at the end.

## 1. Preseed regeneration — human GT untouched
All 30 preseeds regenerated with the corrected segmenter (Plateau-border rejection +
fixed propagation). **All 14 human Foam A masks verified byte-identical** by SHA-256
before/after (preseeds write to a separate directory).

## 2. Before / after region counts
| set | exp | frame | before | after | change | human GT |
|---|---|---|---|---|---|---|
| eval | exp1 | 0 | 359 | **122** | −66% | **124** |
| eval | exp1 | 1 | 353 | **121** | −66% | **122** |
| eval | exp1 | 49 | 239 | 79 | −67% | 84 |
| eval | exp1 | 50 | 237 | 77 | −68% | 80 |
| eval | exp1 | 97 | 176 | 61 | −65% | 63 |
| eval | exp1 | 98 | 178 | **63** | −65% | **63** |
| eval | exp1 | 148 | 126 | 44 | −65% | 46 |
| eval | exp1 | 149 | 124 | 42 | −66% | 43 |
| train | exp1 | 24 | 286 | 92 | −68% | 99 |
| train | exp1 | 25 | 285 | 95 | −67% | 98 |
| train | exp1 | 73 | 202 | 68 | −66% | 70 |
| train | exp1 | 74 | 202 | 69 | −66% | 70 |
| train | exp1 | 120 | 150 | 50 | −67% | 52 |
| train | exp1 | 121 | 154 | 49 | −68% | 52 |
| **eval** | **exp3** | **0** | **1189** | **554** | **−53%** | — |
| **eval** | **exp3** | **1** | 1031 | **525** | −49% | — |
| eval | exp3 | 49 | 1356 | 1112 | −18% | — |
| eval | exp3 | 50 | 1391 | 1154 | −17% | — |
| eval | exp3 | 97 | 1372 | 1172 | −15% | — |
| eval | exp3 | 98 | 1433 | 1242 | −13% | — |
| eval | exp5 | 49 | 644 | 563 | −13% | — |
| eval | exp5 | 50 | 700 | 628 | −10% | — |
| train | exp4 | 0 | 1171 | 1011 | −14% | — |
| train | exp4 | 1 | 994 | 845 | −15% | — |
| train | exp4 | 49 | 1011 | 875 | −13% | — |
| train | exp4 | 50 | 1061 | 935 | −12% | — |
| train | exp6 | 49 | 230 | 197 | −14% | — |
| train | exp6 | 50 | 215 | 178 | −17% | — |
| train | exp7 | 49 | 77 | 74 | −4% | — |
| train | exp7 | 50 | 84 | 81 | −4% | — |

**Foam A is now essentially calibrated**: a uniform −65 to −68% reduction landing within
a few percent of the human counts on every frame (122 vs 124, 121 vs 122, 63 vs 63…).
That is independent confirmation that the Plateau-border gate is correctly tuned.

**Foam C splits in two**: `exp3` f000/f001 drop by ~half (1189→**554**, 1031→**525**),
but every mid/late frame drops only 10–18%.

## 3. Labelability — the decisive evidence
### exp3 f000 (early): looks genuinely correctable
The zoomed overlay (`qc/foamc/exp3_f000_zoom0.png`) shows contours tracing real bubble
rims, with no large bubble subdivided. The dense sub-resolution clusters are left
unlabeled rather than fragmented. 554 regions is still ~1.8× the independent h_maxima
estimate (315 / 274 gas-only), so some over-segmentation remains, but it is the kind a
human can delete.

### exp3 f049+ (mid/late): NOT correctable — it is fragmenting
Two independent lines of evidence:

**(a) The count trend is unphysical.** Foam C is *coarsening*, so bubble count must
**fall**. The preseed does the opposite:

| frame | 0 | 1 | 49 | 50 | 97 | 98 |
|---|---|---|---|---|---|---|
| preseed regions | 554 | 525 | **1112** | 1154 | 1172 | **1242** |
| independent h_maxima estimate | 315 | — | **223** | — | **213** | — |

The preseed **more than doubles** while the independent h_maxima detector **falls**
315 → 223 → 213, which is the physically correct direction. A segmentation whose bubble
count rises through a coarsening sequence is fragmenting, not detecting.

**(b) The overlay confirms it.** In `qc/foamc/exp3_f097_zoom0.png` the red boundaries
wander *through* the interiors of large round bubbles in amoeba-like shapes instead of
following their rims. At f049–f098 the preseed is ~5× the independent estimate.

**Mechanism**: the gas/liquid gate stops separating. At f000 the Otsu threshold is 125.1
and 956/1193 interior blobs are gas-like (80%); by f049 the threshold falls to 115.9 and
**1454/1456 blobs (99.9%)** pass. As the foam drains, the intensity histogram loses its
liquid mode, Otsu lands inside the gas distribution, and essentially nothing is rejected —
while the thinning films let the interior decomposition shatter.

**Correction to an earlier read of mine:** I first took the pale regions at the right of
the f097 crop for label bleed onto background. That is wrong — measured, **0.0%** of
labelled pixels lie outside the foam mask on any frame (Foam A or C), and 0 regions are
majority-background. Those pale areas are large drained regions *inside* the foam.

## 4. Guard behaviour on Foam C — correct, but blind to this failure
The region/eligible-blob ratio is 0.46 (f000) → 0.76 (f049) → 0.80 (f097). Because the
guard now fires on a **relative decline** against its own frame-0 ratio, and this ratio
*rises*, it correctly does **not** false-alarm. Using gas-only blobs as the reference
gives 0.58 / 0.76 / 0.80 — same conclusion.

**But note the honest gap:** the collapse guard is built to catch *under*-segmentation
(the ratchet). Foam C's failure is *over*-segmentation, which the guard cannot see by
construction — a fragmentation guard would need the opposite test (e.g. region count
rising through a coarsening sequence, which is exactly the signal in §3a and would be
cheap to add).

## 5. Verdict and recommendation
**Plainly: `exp3` f000 and f001 are plausibly labelable now; `exp3` f049 onward is not,
and neither are exp4/exp5/exp6 mid frames (they show the same 10–18% drop signature).**

**If you want Foam C ground truth, label the consecutive pair `eval/exp3/f000` and
`eval/exp3/f001`** (554 and 525 regions — about half the work that made you stop, on the
frames where the preseed is visually trustworthy, and consecutive so tracking can be
evaluated too).

**Two caveats on what that would buy.** It gives detection accuracy for Foam C's *dense
early* state — genuinely valuable, and directly comparable to Foam A's F1 0.899. It would
**not** validate the trusted set that feeds the modeling gates, because that set spans all
99 frames and the mid/late frames are the broken ones.

**And a finding that partly answers the original question already:** Foam C's mid/late
segmentation is measurably fragmenting, so **the Foam C von Neumann failure and every Foam
C modeling number rest on unreliable input**. The physics-vs-measurement question for Foam
C is, on this evidence, leaning "measurement" — or at least "not currently measurable".
Fixing the gas/liquid gate for drained foams (a per-frame threshold that does not assume a
bimodal histogram) is the prerequisite, and is probably higher value than labeling.

**Artifacts:** `qc/foamc/{before_after,labelability}.json`, `exp3_f000_zoom0.png`,
`exp3_f097_zoom0.png`, `*_full.png`. Driver: `dev/assess_foamc_labelability.py`.
