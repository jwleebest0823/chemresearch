# Addendum: neighbour-swap (T1) events

Prepared for Dr. Oh, as a follow-on to `results_package/SUMMARY.md`. This covers work
done after that package was sent. Every number here traces to a table in `tables/` or a
figure in `figures/`.

---

## 1. The defect, and its fix

Real 2D coarsening foams undergo neighbour swaps (a film ruptures between two bubbles
while a new film forms between their neighbours — a "T1" event) routinely. Our pipeline
was finding almost none: **1 swap in 198 Foam A frames.** That is not a physical result;
it is implausible on its face and needed resolving before publication.

**Cause: an internal inconsistency, not a real absence.** One part of the pipeline
(building each bubble's neighbour count) had already been repaired to bridge thin,
unlabelled gaps between touching bubbles — a fix validated earlier in the project. The
part that searches for swaps had not been updated to use that same repaired neighbour
graph, so it was working from a map with more missing contacts. Under our detector,
21–25% of the foam's interior area carries no bubble label at all (film and Plateau
border), so two bubbles that are genuinely in contact often have no *pixel* contact.

That matters far more for swap detection than for a simple neighbour count, because
**identifying one swap requires eight separate contact conditions to all be correct at
once** (which pairs are and are not in contact, at two consecutive moments, plus which
bubbles are common neighbours of which). A modest miss rate on any one contact is
tolerable on its own; compounded across eight simultaneous conditions it very nearly
zeroes out detection. Measured: fixing the inconsistency changed the neighbour-contact
count by only **1.18×**, and that alone raised swap detection **24×** — 1 → 22 events on
Foam A.

**Only the consistency fix was shipped.** A further option — loosening how short a
contact can be before it counts as real — was measured (it would raise the count further,
to 35 or 60) but was **not** adopted, because it could not be verified by eye within that
session. See §4 below for what happened when it *was* verified.

---

## 2. Hand-validation

The 22 shipped events were scored by eye, one at a time, against a purpose-built figure
for each: four panels spanning the frame before, the swap frame, and two frames after.
The fourth panel is the important one — a genuine swap's new contact persists and grows;
a one-frame camera or segmentation glitch does not. → `figures/figA0_verified_swap_example.png`

**An earlier verification attempt using only two panels (before/after) was inconclusive**
for exactly this reason: a real swap and a glitch look identical over two frames and only
diverge afterward.

**Result: 0 flicker, 0 unclear, 22 confirmed real. False-positive rate 0/22 (0%), 95%
confidence interval [0%, 14.9%].** The confirmed events include the one shown in
`figA0` — the contact between the separating pair drops from 9 pixels to 0 across one
frame while the new contact grows from 0 to 37 pixels over the following two, and holds.

---

## 3. Swap statistics — reported carefully, because the sample is small

**Rate versus time in the sequence.** → `figures/figA1_t1_rate_vs_tercile.png`,
`tables/t1_rate_vs_time.csv`

| run | early third | middle third | late third |
|---|---|---|---|
| run0 | 0.45 per 100 bubbles/frame | 0.08 | 0.00 |
| run1 | 0.12 | 0.07 | 0.21 |

**Read this cautiously.** 22 events are spread across 6 time bins — several bins contain
only 0 to 2 events — so **individual bin values are not statistically resolvable**; this
is not a resolved rate curve, and none of the six numbers above should be quoted alone.
The one claim the data does support: **swaps concentrate in the dense early foam and
become sparse afterward.** The apparent uptick in run1's final third (0.21) is within
what 1–2 events can produce by chance on a shrinking bubble population and should not be
read as a real late-stage increase.

**Swap-involved bubble size.** → `figures/figA2_size_involvement.png`,
`tables/t1_size_involvement.csv`

Across the 4 bubbles in each of the 22 events (n = 88), the median size of a
swap-involved bubble was **1.01×** the frame's typical bubble size, 95% confidence
interval **[0.55×, 1.52×]**. Read as: swaps do not appear to be a small-bubble-specific
phenomenon — but the interval is wide (nearly 3-fold), so this is a **weak** finding, not
a confident null result.

---

## 4. An open question worth flagging, not yet a correction

While verifying, the 16 events that only appear when the contact-length threshold is
relaxed were also scored, as a check on whether the shipped threshold might be too
strict. **Result: 0 of 16 scored as flicker.** That suggests the current threshold may be
excluding genuine swaps and costing real recall.

This is reported as an **open question for a follow-up session**, not a change made now:
the shipped detector was not touched, and no swap-rate conclusion above uses these 16
events.

---

## 5. A methodological note — a bug caught during this analysis

Worth including because it is the same class of failure this project has repeatedly
found and fixed: **the first attempt to compute the rate table above silently produced
zero for every run1 event.** The cause was a unit mismatch — one internal table indexed
video frames starting over at zero for each recording run, while the hand-scoring sheet
indexed frames continuously across the whole sequence. Comparing the two directly
matched nothing for run1 and printed zeros rather than an error, which would have
**wrongly suggested that swaps stop entirely partway through the sequence** — an
artifact of the bug, not a physical result.

Fixed by putting every frame reference on the same footing, and — because a silent zero
is worse than a crash — two checks were added that make the analysis refuse to run
silently: one confirms every scored event lands in exactly one time bin, the other
confirms the bins' totals match the number of events actually scored. Both now pass and
are printed as part of the analysis output.

---

## Reproducing

`dev/t1_score_analyze.py` (rate + size tables, with the guards described in §5) →
`dev/t1_addendum_figures.py` (this package's figures). Source verification figures for
all 22 events plus the 16 threshold-relaxation events: `qc/t1_verify/` (not included
here — regenerable, not a committed research artifact on its own).
