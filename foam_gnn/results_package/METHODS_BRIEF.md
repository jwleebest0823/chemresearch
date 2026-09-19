# Methods brief

One page, in pipeline order. Details and every `# DECISION` justification live in the
repository under `docs/`.

## Imaging

Quasi-2D soap-foam rafts between plates, brightfield, illuminated from below. 8-bit
grayscale, 1024×1280 px. Colour is a non-physical sensor cast and is discarded — no film
thickness is inferable from intensity. Frame interval 30 s (Foams A, C) or 10 s (Foam F).
No pixel-size calibration, so areas are px² and rates px²/s; the physics of interest is
scale-free. Foam A is one raft in two runs separated by a 2.5-min gap; identities are
never matched across that gap. Foam C is one raft; Foam F is an independent raft.

## Detection

**Cellpose-SAM, zero-shot** — no foam-specific training. Inference on GPU (Colab);
~13 s/frame, versus ~64 min/frame on the available CPU, which is why it is run externally
and the label maps imported.

**One post-processing step.** Raw Cellpose also segments the background plate into
blobs (on one frame, 335 of 377 "objects" were plate). Objects are kept only if ≥50% of
their pixels fall inside an independently computed **foam mask** — edge-density map →
Li threshold → morphological close → largest connected component → fill holes, taken from
the raw image and never from Cellpose's output, so it cannot be tuned to flatter the
detector. The criterion is a majority vote and is inert between 0.10 and 0.90 (measured),
i.e. not a tuned threshold.

**The foam mask is a detection filter only, not a measure of where the foam ends.** It
leaks past the outermost bubbles onto empty plate (11% of Foam A's mask, 8% of C's, 25% of
F's lies outside the bubbles' convex hull; in Foam F part of that band also holds rim
bubbles the detector missed). # DECISION (Sept. 18): every edge-based quantity — the
perimeter/interior split, wetness measures, the "interior" neighbour count — is measured
from the **raft edge**, the convex hull of the detected (or hand-labelled) bubbles. Two
rules use that edge, for different purposes: for the perimeter-K results a bubble is on the
perimeter if its **centroid** is within 2 equivalent radii of the detected-bubble hull; for
the detector calibration (neighbour counts) a bubble is interior only if the **whole
bubble** lies more than one median hand-labelled radius inside the hand-labelled hull, so
that all three detectors are scored on the same pixels. The earlier foam-mask rule missed
26% (A), 59% (C) and 38% (F) of genuine rim bubbles, and the results that used it are
withdrawn in `SUMMARY.md` §3, §5 and §7.

Detection was **not** expanded to tile the foam. That was implemented and rejected: the
hand labels leave space between bubbles unlabelled (it is film and Plateau border), so
expansion moved areas and neighbour counts *away* from truth and cost 0.12 F1. *(The
figure previously quoted here, 25% of the foam interior, was measured over the leaky foam
mask; inside the raft, excluding a one-radius margin, the hand labels leave 11.4%
unassigned. The rejection does not depend on that number.)*

## Tracking

Per-frame detections are linked into identities by overlap and centroid/area cost, with:
merges inheriting the larger parent's identity (never minting a new one); a dormancy
window so a one-frame detection dropout is not a death; and retroactive retirement of
identities whose separation does not persist. **Neighbour graphs use gap-bridged
adjacency**: each unlabelled pixel within a per-frame, scale-adaptive distance is assigned
to its *nearest* label before adjacency is measured, so two bubbles sharing a thin film
count as neighbours. Over-bridging is structurally impossible — nearest-label assignment
means an intervening bubble always separates two non-neighbours.

## Trusted set

Physics is fitted only on identities the tracker follows reliably: bubbles present in the
first frame, in runs of ≥5 consecutive frames with no gap, no merge, and no large
area jump. A **dropout-and-recovery filter** additionally removes V-shaped area traces
(a large drop that returns to its prior value within two frames) — a real bubble cannot
lose 40% of its area and get it back. This is survivorship selection by construction and
is not an unbiased sample for absolute coarsening rates; it is valid for the within-set
comparisons reported.

## Estimating K, and why least squares was rejected

The model `dA/dt = K·(n − 6)` is a line **through the origin** (a hexagon neither grows
nor shrinks), so K is a through-origin slope. Least squares weights every measurement by
`(n − 6)²`, which on this data gave **1.2% of rows 48% of the fit weight** — those rows
being giant flickering bubbles — and ~~flipped K's sign~~ made K fail the sign test at short
horizon (+0.14 with an interval spanning zero; corrected Sept. 18).

**Shipped estimator: the median of the per-point slopes, `median(y/x)`** — the natural
robust analogue of a through-origin fit, since each point contributes one independent
slope through the origin. Benchmarked against a known K = 0.35 over 200 replicates: at
the contamination rate measured in the data, least squares was biased −0.093 with an
inter-replicate spread of 1.04 (i.e. unusable at a quantity of size 0.35), while the
robust estimator was unbiased with spread 0.009. Theil–Sen is reported as an independent
cross-check. ~~It agrees throughout.~~ *Corrected Sept. 18:* it agrees for Foam A; it is
1–17% higher for Foam C and 24–77% higher for Foam F, outside the robust estimator's interval
at 30 s and 150 s in both (`tables/K_fits.csv`), and it gives Foam F a steeper horizon decline (1.95×
against 1.59×). Least squares is still reported alongside, so the
difference is visible rather than hidden.

## Horizons and time units

**Prediction horizons are specified in SECONDS and matched across foams**, never in
frame counts. dA/dt is computed as ΔA divided by the elapsed time between the two
frames, taken from the image filename timestamps, so it is always px² per second
regardless of acquisition rate. This matters because the foams are not imaged at the
same rate — Foams A and C at 30 s/frame, Foam F at 10 s/frame — so a horizon of "20
frames" would mean 600 s in A and C but only 200 s in F. Every K reported here is
fitted at 30 / 150 / 600 s: horizons of 1 / 5 / 20 frames for A and C, and 3 / 15 / 60
frames for F. Frame intervals were verified from the filename timestamps rather than
assumed from configuration.

## Uncertainty and out-of-sample testing

Every interval on **K** is a **cluster bootstrap resampling whole bubbles**, not individual
rows: a bubble's measurements are correlated across frames, and resampling rows would fake
significance. 1000 resamples, 95% percentile intervals. *(Corrected Sept. 18 from "every
confidence interval".)* Per-frame measures — wetness, circularity, detector calibration —
are bootstrapped over **frames**, because bubbles within a frame are not independent. Event
rates (neighbour swaps) use exact Poisson intervals, and the 0/22 false-positive rate a
Wilson interval.

Every comparative claim is **out-of-sample**. K is fitted on one epoch or session and
scored on a held-out one; model comparisons use leave-one-**foam**-out, with a foam's
sessions never split across train and test. "Beats persistence" is a paired bootstrap on
the *difference* in error under the same resampled bubbles, and requires the whole
interval to favour the model — interval overlap alone is only a weak proxy.

## Reproducibility

172 automated tests. The 14 ground-truth masks are checksum-verified unmodified at the
end of every session. The figures and tables in this package are built by
`build_results_package.py`, except `fig5_verified_T1_swap.png` (drawn by
`dev/t1_event_figure.py`) and the figures shared with the revised paper, which are copied
from `paper_figures/` (drawn by `dev/paper_figures.py`; run it before the build). The
analysis drivers (`dev/`) and their intermediate tables (`qc/`) are local and not in the
repository; every table a figure or caption reads is copied into `tables/`.
