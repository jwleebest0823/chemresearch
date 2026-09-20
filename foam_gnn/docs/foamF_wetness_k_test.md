# Is there a measurable wetness–K relationship in Foam F?

**Verdict: the association is there and strong in sign, but it carries almost no
information — and the one test that does carry information says wetness is not sufficient.**

1. **The correlation cannot be resolved, and in Foam F it is arithmetically forced.**
   Across Foam F's five usable windows, Spearman ρ(K, wetness) = **−0.90** (junction size)
   and **−1.00** (brightness). But K's rank order across those windows is *exactly* elapsed
   time order (ρ(K, t) = +1.00), which makes ρ(K, wetness) **identically ρ(time, wetness)** —
   the numbers are equal to the digit (−0.90 = −0.90, −1.00 = −1.00). The correlation
   therefore restates the wetness–time collinearity and says nothing new about K. With five
   windows an exact permutation test can only reach p < 0.05 for a *perfectly* monotone
   relation; with three or four windows nothing is resolvable at all.
2. **The timing is measurable, and the two wetness measures disagree about it.** K crosses
   zero at **402 s** [348, 469] (402–465 s across window schemes). It sits **+78 s** after
   the junction-size half-decay (325 s [281, 379]) — inside the 300 s granularity of the
   crossing estimate and flipping between "resolved" and "not resolved" depending on how
   the half level is bootstrapped, so **coincident within resolution, not a measured lag**
   — and **−133 s before** the brightness half-decay (535 s [508, 686]), where the sign is
   stable under both constructions (P ≈ 0.998). The measures are not interchangeable
   clocks: at 590 s the junction measure has completed 89% of its decay and the brightness
   measure 53% (at 740 s, 94% and 61%).
3. **The decisive test: in Foam F, K rises while its wetness change is not resolvable.**
   After the junction measure comes within 10% of its plateau:

   | foam | wetness change over the window | resolved? | K over the window | ratio | P(ratio ≤ 1) |
   |---|---|---|---|---|---|
   | **F** | −0.0083 [−0.0152, **+0.0010**] | **no** | +1.489 → +1.951 | **1.31** [1.01, 1.75] | 0.021 |
   | C | −0.0048 [−0.0089, −0.0029] | yes | +0.211 → +0.133 | **0.63** [0.52, 0.75] | 1.000 |
   | A | −0.0092 [−0.0132, −0.0047] | yes | +0.466 → +0.317 | 0.68 [0.16, 1.40] | 0.843 (unresolved) |

   **Foam F's K rises by 31% over a stretch where its own wetness change is not resolvable
   from zero** (P(ratio ≤ 1) = 0.021). Foam C's K *falls* by 37% over a small but resolved
   drying — so once each foam has dried, K keeps moving, upward in one and downward in the
   other. **No single function K(wetness) fits both**, and in Foam F wetness is not needed
   for K to move. (Foam A is unresolved in both directions and carries no weight.)

Driver: `dev/wetness_k_correlation.py`; wetness on a dense grid from `dev/wetness_dense.py`
(which reproduces the published 20-frame values exactly on every shared frame). Artifacts:
`qc/wetness_k/`.

---

## 1. Windows, and what the 20-bubble floor allows

Foam F has **56 tracked bubbles in total** and its trusted count falls below 20 after about
1530 s, so late windows are underpowered by construction. Windows are **refused, not
fitted**, and the reason is recorded: every Foam F refusal is `bubbles<20`, never missing
wetness.

| scheme | usable | refused (reason) |
|---|---|---|
| thirds (740 s) | 3 of 3 | — |
| quarters (555 s) | 3 of 4 | last: 16 bubbles |
| fifths (444 s) | 4 of 5 | last: 13 bubbles |
| **sixths (370 s) — primary** | **5 of 6** | last: 8 bubbles |
| sliding 600 s / step 300 s (timing only) | 6 of 7 | from 1800 s: 13 bubbles |

> `# DECISION (primary windows = equal sixths).` Thirds cannot locate a transition inside
> the first third. Sixths are the finest equal partition where most windows clear the floor.
> `# DECISION (sliding windows are used only for timing)`, never as correlation samples,
> because overlapping windows are not independent points.
> `# DECISION (window wetness = median of the dense-grid frames inside it)`, matching how
> every other wetness number in the project is formed; intervals resample those frames.
> `# DECISION (Foam A's wetness grid covers both runs, 0–5999 s).` The published 20-frame
> file samples run0 only (0–2850 s). Pairing that against K windows spanning the whole
> sequence refused Foam A's later windows for want of wetness rather than bubbles, and
> **misplaced its plateau onset at 750 s instead of 3119 s** — which reversed its
> post-plateau result. Extending the grid fixed it; the first version of this document
> reported Foam A rising 1.44× [1.24, 1.68], which was an artifact of the truncation.

**Foam F, primary windows** (30 s horizon; K intervals are cluster bootstraps resampling
whole bubbles, which are shared between windows — 56 in total):

| window | bubbles | junction size | brightness | K |
|---|---|---|---|---|
| 0–370 s | 56 | 0.649 | 0.474 | **−0.700** [−1.050, −0.467] |
| 370–740 s | 43 | 0.258 | 0.388 | +1.067 [0.600, 1.528] |
| 740–1110 s | 34 | 0.191 | 0.338 | +1.417 [0.866, 1.799] |
| 1110–1480 s | 25 | 0.176 | 0.325 | +1.751 [1.233, 2.233] † |
| 1480–1850 s | 23 | 0.181 | 0.298 | +1.892 [1.166, 2.377] † |
| 1850–2220 s | **8** | 0.174 | 0.259 | **refused** (no interval is computed) |

† These two windows clear the floor on the point estimate (25 and 23 bubbles) but their
*bootstrap replicates* mostly do not: the median replicate holds 16 and 15 distinct bubbles,
and 96% and 99% of replicates fall below the 20-bubble floor. Their intervals should be read
as wide for that reason, and the project's floor is applied to the point estimate only.

## 2. The correlation, and why it is uninformative

Sixths, all three foams (A and C are controls run through the identical procedure):

| foam | measure | windows | Spearman ρ | exact p | ρ(K, t) | ρ(wetness, t) |
|---|---|---|---|---|---|---|
| **F** | junction size | 5 | **−0.90** [−1.00, −0.60] | 0.083 | **+1.00** | −0.90 |
| **F** | brightness | 5 | **−1.00** [−1.00, −0.40] | 0.017 | **+1.00** | −1.00 |
| C | junction size | 6 | +0.43 [−0.09, +0.77] | 0.419 | −0.66 | −0.83 |
| C | brightness | 6 | +0.66 [+0.13, +0.83] | 0.175 | −0.66 | −1.00 |
| A | junction size | 6 | −0.83 [−1.00, −0.03] | 0.058 | +0.83 | −1.00 |

(Smallest |ρ| an exact test can resolve: 1.00 at five windows, 0.886 at six. So none of
these rows is resolved, including Foam A's −0.83 at p = 0.058.)

**Why Foam F's number is empty.** Because ρ(K, t) = +1.00 *exactly*, K's rank vector is the
time rank vector, so ρ(K, wetness) **is** ρ(time, wetness) — not approximately, identically.
The correlation measures the wetness–time collinearity, which is a property of the
experiment, not of K.

This forcing needs |ρ(K, t)| = 1 and so does **not** apply to Foams C and A. Enumerating all
six-window rank vectors consistent with Foam C's observed ρ(K, t) = −0.66 and
ρ(wetness, t) = −0.83, its ρ(K, wetness) could have fallen anywhere in [+0.14, +0.94]; the
observed +0.43 is one of fifteen possible values. So Foam C's correlation is not forced —
but it is also not resolved (its interval spans zero).

**And its positive sign is not an opposite-sign wetness response.** Split Foam C by phase:
over its own drying (first three sliding windows, junction 0.220 → 0.154) ρ(K, wetness) =
**−1.0**, the *same* sign as Foam F, with K rising +0.167 → +0.244. The positive
whole-sequence value comes entirely from the four later windows sitting on C's plateau,
whose wetness medians (0.145, 0.141, 0.139, 0.139) differ by less than their own bootstrap
intervals while K falls steadily to +0.133. **During drying the two foams agree in sign;
they differ in what K does afterwards** — which is the post-plateau test of §4, not a
contrary wetness response.

**Power.** With five windows the smallest |ρ| an exact permutation test can call significant
at p < 0.05 is **1.00**; with six it is 0.886; with four the best achievable p is 0.083 and
with three 0.333, so **no correlation is resolvable below five windows whatever its value**. Foam F's brightness
result reaches p = 0.017 only by being exactly monotone, and even that is optimistic —
windows share bubbles and are consecutive in time, so they are not the independent samples
a permutation test assumes. **Treat every correlation here as unresolved.**

## 3. Timing: coincide, lag, or precede?

| quantity | t (s) | 95% CI |
|---|---|---|
| K zero crossing (sliding 600 s / 300 s) | **402** | [348, 469] |
| — window 600 s / step 150 s | 465 | [362, 533] |
| — window 450 s / step 150 s | 435 | [360, 505] |
| — window 740 s / step 370 s | 445 | [383, 516] |
| junction-size half-decay | **325** | [281, 379] |
| brightness half-decay | **535** | [508, 686] |
| **K crossing − junction half-decay** | **+78** | [−0.3, +165], P(≤0) = 0.026 |
| — same, half level held fixed | +78 | [+7, +166], P(≤0) = 0.014 |
| **K crossing − brightness half-decay** | **−133** | [−304, −67], P(≤0) = 0.998 |
| — same, half level held fixed | −133 | [−196, −68], P(≤0) = 0.998 |

The K rows resample **whole bubbles** (cluster bootstrap, 2000 replicates); the half-decay
rows resample the 46 dense wetness **frames**; the difference rows pair the two
element-wise.

K's sign change sits **between** the two measures' half-decays: after the junction structure
has half-collapsed, before half the liquid (by brightness) has gone.

**The junction "lag" is not a resolved lag.** Its interval touches zero under the primary
construction and clears it under the level-fixed one (P(no lag) = 0.026 and 0.014), so the
verdict flips with a defensible change of procedure — and across re-runs with fresh seeds
the lower bound moves either side of zero. More decisively, +78 s is well inside the 300 s
granularity of the crossing estimate. **Read it as coincident within the resolution of this
measurement, not as a measured lag.** The brightness comparison is different: K precedes
that half-decay by 133 s under both constructions, with P ≈ 0.998, and 133 s is comparable
to the granularity but the sign is stable.

**Caveat on resolution.** The crossing is interpolated between window centres, so its
granularity is the step: 300 s in the primary scheme, and 150 s, 150 s and **370 s** in the
three sensitivity runs (the last is coarser than the primary, not finer, and its interval
conditions on the 97% of replicates in which a crossing exists at all). The estimate is
stable across schemes (402–465 s), but differences below ~150 s should not be over-read —
which includes the +78 s junction lag.

**Caveat on the half-decay interval, and why both are reported.** Each replicate
re-estimates the half threshold as well as the curve, because the threshold is itself
measured from the data — the bootstrap of the whole estimator. Holding the level fixed
instead isolates the crossing and gives narrower intervals: the junction difference moves
from [−0.3, +165] to [+7, +166] and the brightness difference from [−304, −67] to
[−196, −68] (`qc/wetness_k/timing.csv` carries both rows). The junction verdict changes
between them, which is precisely why neither is presented alone.

**The two measures disagree about the drying window** (`qc/wetness_k/decay_fractions.csv`).
At 590 s the junction measure is 89% decayed and the brightness measure 53%; at 740 s, 94%
and 61%. The junction measure collapses early then saturates near the pixel resolution; the
brightness measure keeps falling nearly linearly to the end of the sequence.

## 4. The confound, and what would break it

In Foam F wetness and elapsed time are collinear (|ρ| ≈ 1), so **no within-F correlation can
separate them.** What would:

* **A foam that re-wets, or whose wetness is non-monotone in time.** None of the six foams
  in this project does.
* **Two foams with the same wetness trajectory over different elapsed spans**, or the same
  span with different trajectories — an experiment designed to decorrelate them.
* **An intervention** setting humidity or evaporation independently of foam age. This is the
  only clean route and needs new data.

**What the existing data can do:**

* **The post-plateau test.** In Foam F, K rises 31% (P(ratio ≤ 1) = 0.021) while its
  wetness change is **not resolved** (−0.008 [−0.015, +0.001]) — K moves without a
  detectable wetness change. In Foam C, K falls 37% over a small resolved drying, i.e.
  **drier accompanies lower K** once C has dried, while during C's actual drying the sign
  matches Foam F's (§2). The implied local sensitivities have opposite signs (C +16.3
  [+6.5, +30.7]; F −55.8, unresolved [−362, +131]), so a single monotone K(wetness) cannot
  fit both phases. Foam A is unresolved either way (0.68 [0.16, 1.40]) and carries no
  weight here.
* **Matched wetness across foams.** At comparable junction wetness the foams do not agree
  on K, even after Task 1's standardisation (K* = K/A_char, so magnification and coarseness
  are divided out):

  | foam | window | junction wetness | K* (10⁻⁴ s⁻¹), yardstick-exact interval |
  |---|---|---|---|
  | F | 600–1200 s | 0.191 | +4.24 [2.66, 5.44] |
  | C | 0–600 s | 0.220 | +2.14 [1.71, 2.56] |
  | F | 300–900 s | 0.246 | +2.86 [1.50, 4.30] |

  **These intervals treat A_char as exact**, which is the form Task 1 reports alongside but
  does *not* adopt; the adopted joint intervals, which also resample the frames A_char is
  measured on, are about 27% wider. As printed the Foam F (0.191) and Foam C (0.220)
  intervals are disjoint by 0.10; under the joint intervals they overlap. Either way only
  one Foam C window falls inside Foam F's range, so this comparison is suggestive at best.

## 5. What this does and does not support

**Supported.** Foam F's K and its wetness move together over its first ten minutes, in the
direction the physical story predicts, and the sign change falls inside the drying window
(402 s [348, 469], inside 0–740 s). Foam C's drying phase moves the same way, which is the
one piece of cross-foam support the data give.

**Not supported.** That wetness *drives* K. The correlation is identically the
wetness–time collinearity; it is not resolvable at the available window count; K rises 31%
in Foam F with no detectable wetness change; and once each foam has dried, K keeps moving —
upward in Foam F, downward in Foam C — which no single function of wetness produces.

**Recommendation.** Keep the published *timing* wording (Figures 1, 3 and 4), which is a
coincidence claim and is exactly what these data support. Do **not** upgrade it to a
correlation or a mechanism, and do not add a figure: a five-point correlation that cannot be
resolved should not be drawn as a relationship.

## 6. Published statements: what was changed today

Three files were edited (not silently — each carries a dated note):

| file | change |
|---|---|
| `docs/wetness_and_k_fragility.md` | The bullet "**The wetness mechanism is supported for Foam F specifically**" is struck through and given a dated *Narrowed 2026-09-19* block: the timing coincidence holds, "mechanism" does not. |
| `results_package/SUMMARY.md` §7 | New paragraph "Does wetness actually drive K? Tested directly…", reporting the crossing time, the collinearity, and the post-plateau result. |
| `paper_figures/README.md` (Figure 4) | New paragraph recording that the relationship was tested, that the caption's timing wording is what survives, and that no figure is drawn. |

Statements left standing, and one to qualify:

| where | statement | status |
|---|---|---|
| Figure 4 caption, `SUMMARY.md` §7 | "That wet window falls inside the first third … where Foam F's K is negative" | **stands** — now measured: K crosses zero at 402 s [348, 469] |
| Figure 3 caption, `SUMMARY.md` §7 | "a first third that contains its wet phase, with negative K … and a drier remainder with K ≈ +1.6" | **stands**, with the addition that K keeps rising 31% [2%, 69%] after wetness plateaus |
| Figure 4 caption, `SUMMARY.md` §7 | "the brightness fraction … also falls over the same ten minutes (0.53 to 0.38)" | **qualified today** in all three places (caption, SUMMARY, README): true as far as it goes, but the brightness measure is only 53% decayed at 590 s and keeps falling to 0.25 by the end, so it does not corroborate a drying window confined to ten minutes |

## 7. Limitations

* **56 bubbles, 5 usable windows.** The binding constraint; no windowing fixes it.
* Foam F has **no hand-labelled ground truth**, so both its K and its wetness are
  detector-dependent, and its earliest junction values are upper bounds (some junction discs
  enclose bubbles the detector missed, Supplementary Figure S3).
* Windows share bubbles, so permutation p-values are optimistic and window intervals are
  correlated. In Foam F's two latest usable windows, most bootstrap replicates hold fewer
  than 20 distinct bubbles even though the point estimates clear the floor.
* The plateau criterion (first frame within 10% of the plateau) is a definition, not a
  fitted transition. It is also sensitive to how far the wetness series extends — which is
  exactly what went wrong for Foam A in the first version of this analysis, where a
  truncated wetness grid put A's plateau at 750 s instead of 3119 s and produced a
  "resolved" rise that does not survive the fix.
* Interval constructions are stated where they matter (bubbles vs frames; half level
  re-estimated vs fixed), because the junction-lag verdict changes between them. Where a
  verdict depends on the construction, this document reports both rather than choosing.
