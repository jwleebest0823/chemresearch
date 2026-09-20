# Standardising K against magnification: what can and cannot be done

**Verdict up front, in three parts.**

1. **The premise is correct: there is no scale calibration anywhere.** No µm/px, no
   objective, no scale bar, no acquisition record, in any image, filename, config or
   document. K in px² s⁻¹ is therefore only comparable across foams up to an unknown
   per-foam factor. `PipelineConfig.data.microns_per_px` is `None` and is read by nothing.
2. **But the premise's implied cause is not what the images show.** Testing it needs a
   scale proxy that does not depend on how fine the foam is. The raft — the convex hull of
   the detected bubbles — is one. **Foam C's bubbles are 0.57× Foam A's radius while Foam
   C's raft is 1.44× Foam A's.** A magnification difference moves both together, so it
   cannot be the main story. The foams differ structurally: Foam C holds **432 bubbles per
   raft** against Foam A's **87** and Foam F's **61**, a magnification-invariant count.
3. **Standardising is implemented and reported, and the answer depends on the yardstick.**
   Dividing by the foam's own characteristic bubble area (`K* = K / A_char`, s⁻¹) narrows
   the cross-foam spread from 3.37× to 1.48× **and inverts the A-vs-C ordering**. Dividing
   by the raft area — the yardstick that would be a magnification correction if the rafts
   are physically comparable — *widens* it to 5.15×. Both are magnification-invariant.
   They disagree, and nothing in the data chooses between them.

**Nothing within a foam changes.** With a fixed per-foam `A_char`, K* is K times one
positive constant, so Foam F's sign change, Foam A's 1.5× rise and Foam C's 1.5× fall are
preserved exactly — verified, not assumed, below. The paper's headline claim ("K is not a
per-foam constant; it varies over a foam's lifetime") is a within-foam claim and is
untouched.

Drivers: `dev/scale_metadata_probe.py`, `dev/scale_evidence.py`, `dev/k_standardised.py`.
Artifacts: `qc/scale/`, `qc/k_standardised/`.

---

## 1. What is actually known about each foam's scale

`dev/scale_metadata_probe.py` opens **every** frame of each foam (198 / 99 / 503) and
reports the distinct metadata, then looks for a ruler in the images themselves.

| | Foam A (exp1) | Foam C (exp3) | Foam F (exp10) |
|---|---|---|---|
| frames | 198 | 99 | 503 |
| format, size | JPEG 1280×1024 | JPEG 1280×1024 | JPEG 1280×1024 |
| EXIF tags | **0** | **0** | **0** |
| JFIF density | 48 dpi | 60 dpi | 60 dpi |
| acquired | 2021-01-18 | 2026-06-16 | 2026-07-12 |

* **No absolute calibration exists.** No EXIF at all (the only metadata segment in these
  JPEGs is the 16-byte JFIF header), no scale token in any filename or directory, no
  sidecar file, no lab record in the repository, and no code path that converts px to a
  physical unit.
* **The JFIF density is not a scale.** It is a print-resolution hint. Taken literally, 48
  dpi means 529 µm/px, which would make the frame 677 mm wide. It also tracks the
  acquisition era, not the optics: every 2026 session (exp3–exp10) reads 60 whatever the
  foam looks like, and only the 2021 session reads 48.
* **Foam A alone contains a physical ruler.** Its frames carry the graph-paper grid the
  pipeline already notches out (`config.py:15`, "a periodic ~18.3 px grid"). Measured from
  the power spectrum against a local background, Foam A has a sharp square lattice at
  **18.27 px and 18.26 px in two orthogonal directions** (87.5° and 176.9°), 37–78× above
  background, and **identical at frame 0 and frame 99**. Foams C and F have no such thing:
  their strongest sharp peaks are 14–16× and their period *moves* between frames (C 13.5 →
  75.3 px; F 22.5 → 15.3 px), which is the foam's own spacing coarsening, not a ruler.

> **The one action that would convert Foam A to physical units.** If you can tell us the
> pitch of that graph paper, Foam A is calibrated exactly: 18.27 px per square. For 1 mm
> paper that is 54.7 µm/px and Foam A's K = 0.367 px² s⁻¹ becomes **1.10 × 10³ µm² s⁻¹**;
> for 2 mm paper, 4.39 × 10³ µm² s⁻¹. **Foams C and F cannot be calibrated this way** — no
> ruler is visible in them — so this would give physical units for one foam, not a
> cross-foam comparison.

## 2. Testing the premise: is the bubble-size difference magnification?

Bubble size cannot answer this, for the reason the mentor states: a smaller median radius
means lower magnification **or** a finer foam, and these are not separable. The raft can:
its size in px is set by magnification and by how big the physical raft was, but **not** by
how fine the foam is. `dev/scale_evidence.py` measures both on every frame (bubbles) and
every fifth frame (raft hull), over all frames of each foam.

First period (median over frames; 95% bootstrap intervals over frames in `qc/scale/summary.csv`):

| measure | Foam A | Foam C | Foam F | what it is |
|---|---|---|---|---|
| median bubble radius | 27.5 px | 15.8 px | 31.6 px | scale × fineness |
| median bubble area | 2384 px² | 781 px² | 3143 px² | scale² × fineness² |
| raft radius (hull) | 312 px | **448 px** | 363 px | scale × physical raft size |
| **bubbles per raft** | **87** | **432** | **61** | **dimensionless** |
| **bubble radius ÷ raft radius** | **0.089** | **0.035** | **0.086** | **dimensionless** |
| raft filled by bubbles | 0.91 | 0.84 | 0.64 | dimensionless |

**Read the third and fourth rows together.** If Foam C were simply Foam A at lower
magnification, its bubbles *and* its raft would both be smaller in pixels. Its bubbles are
1.75× smaller and its raft is 1.44× **larger**. No single magnification factor does that.

The two dimensionless rows need no assumption at all: **Foam C's bubbles are 2.5× finer
relative to its own raft than Foam A's, and it holds five times as many of them.** Foam F
sits almost exactly on Foam A's ratio (0.086 vs 0.089) — F and A are similar foams
differently sized on the sensor, while C is a genuinely different, much finer foam.

If you additionally assume the physical rafts are comparable between experiments — plausible
(same plates, similar drop) but **not verified, and not verifiable from these images** —
then the raft ratios give the relative magnifications directly: **C was imaged at 1.44× Foam
A's magnification and F at 1.16×.** Under that assumption a magnification correction makes
Foam C's K *smaller* relative to Foam A, widening the raw gap rather than closing it.

So the mentor's statement "the raw cross-foam comparison is partly comparing microscope
settings" is true, but incomplete: it is also, and by more, comparing foams that genuinely
differ in fineness. Separating the two needs one calibration number per foam that does not
exist.

## 3. The dimensionless form, and the choice of A_char

`K* = K / A_char`, units s⁻¹, magnification-invariant whatever the magnification was.

> `# DECISION (A_char is a FIXED per-foam reference area, not per-frame).` The reference is
> the median detected-bubble area over the foam's **first period** — the first third of its
> elapsed time, the same split `k_robustness.py` uses for K by period. A per-frame A_char
> grows as the foam coarsens, so dividing by it absorbs part of the signal being measured.
> With a fixed reference, K* is K times one positive constant, so every within-foam
> comparison is preserved exactly.
>
> `# DECISION (A_char is measured on ALL DETECTED bubbles, not the trusted rows).` The
> trusted set is survivorship-selected toward larger, longer-lived bubbles (its median
> radius already exceeds the detected median at frame 0 in every foam, and the gap widens
> with time), so its median area is not the foam's characteristic bubble area.
>
> `# DECISION (interval).` K* is a ratio of two measured quantities, so each bootstrap
> replicate resamples **both** — whole bubbles for K (the project's cluster bootstrap, 1000
> replicates) and frames for A_char — and the interval is the percentile interval of the
> ratio. This matters more than expected: treating A_char as exact would make the interval
> a median of 21% narrower (the joint interval is 27% wider, up to 123% wider for Foam F's
> short windows), so **the yardstick carries a material share of K*'s uncertainty**. Both
> forms are in `K_star.csv` (`K_star_ci_*` joint, `K_star_ci_*_fixedA` yardstick-exact).

A_char values: **A 2384 px², C 780 px², F 3143 px²** (`qc/k_standardised/a_char.csv`).

**The per-frame variant was computed rather than dismissed**, and it behaves exactly as the
mentor predicted — which is why it is not adopted:

| foam | fixed A_char (adopted) | per-frame A_char |
|---|---|---|
| A, first → last third | +1.26 → +1.78 → +1.89 (rises 1.50×) | +1.26 → +1.64 → +1.58 (**rise reverses at the end**) |
| C, first → last third | +2.56 → +2.52 → +1.71 (falls 1.50×) | +2.58 → +1.71 → +0.97 (**fall steepens to 2.7×**) |
| F, first → last third | −0.95 → +4.99 → +5.20 | −1.19 → +3.75 → +3.88 |

(units 10⁻⁴ s⁻¹, 30 s horizon). The per-frame yardstick makes Foam A's monotone rise
non-monotone and nearly doubles Foam C's apparent decline, because the divisor is itself
growing. A fixed reference cannot do that.

## 4. Results — K and K*, all foams, all horizons

`qc/k_standardised/K_star.csv`. The raw K column reproduces the published values exactly
(guarded: the script fails if any value differs from `K_fits.csv` or `K_by_period.csv`).

**Pooled, by horizon** (95% intervals; K* in 10⁻⁴ s⁻¹):

| horizon | | Foam A | Foam C | Foam F | spread |
|---|---|---|---|---|---|
| 30 s | K, px² s⁻¹ | +0.3667 | +0.1776 | +0.5995 | 3.37× |
| | **K\* = K/A_bubble** | **1.54** [1.32, 1.69] | **2.28** [1.98, 2.54] | **1.91** [1.25, 2.80] | **1.48×** |
| | K/A_raft, 10⁻⁶ s⁻¹ | 1.20 | 0.28 | 1.45 | 5.15× |
| | K/median\|dA/dt\| | 0.50 | 0.38 | 0.14 | 3.53× |
| 150 s | K, px² s⁻¹ | +0.3643 | +0.1800 | +0.4900 | 2.72× |
| | **K\*** | **1.53** [1.31, 1.68] | **2.31** [2.04, 2.60] | **1.56** [0.78, 2.74] | **1.51×** |
| 600 s | K, px² s⁻¹ | +0.3583 | +0.1933 | +0.3764 | 1.95× |
| | **K\*** | **1.50** [1.29, 1.66] | **2.48** [2.18, 2.80] | **1.20** [0.39, 2.49] | **2.07×** |

**By period** (30 s horizon; K* in 10⁻⁴ s⁻¹):

| foam | first third | middle third | last third | |
|---|---|---|---|---|
| A | +1.26 [1.09, 1.44] | +1.78 [1.51, 1.96] | +1.89 [1.49, 2.31] | rises 1.50× |
| C | +2.56 [2.21, 3.06] | +2.52 [2.14, 2.77] | +1.71 [1.57, 2.06] | falls 1.50× |
| **F** | **−0.95** [−1.89, −0.08] | **+4.99** [3.60, 6.31] | **+5.20** [3.65, 7.81] | **changes sign** |

### Does the ordering change? Yes — and it depends on the yardstick

* Raw px² s⁻¹ at 30 s: **F > A > C** (F 1.6× A, A 2.06× C).
* K* (÷ bubble area): **C > F > A** — Foam C moves from lowest to highest, 1.48× Foam A,
  and the two intervals do not overlap, so the inversion is resolved *given this yardstick*.
* K/A_raft (÷ raft area): **F > A > C**, with the A-to-C gap *widened* to 4.3×.
* The existing D4 form (÷ median |dA/dt|): A > C > F, and at 600 s A and C agree to 2%.

Four magnification-invariant summaries, three different orderings. **That is the finding:
the cross-foam ordering of K's magnitude is not established by these data.** What survives
is the structural statement of §2 (bubbles per raft 87 / 432 / 61) and every within-foam
result.

### Do the sign change and the period trends survive? Yes, exactly

With a fixed positive A_char, K* = K × constant, so signs and within-foam ratios are
preserved identically: Foam A rises 1.50×, Foam C falls 1.50×, Foam F crosses zero, in both
columns above. This was verified numerically rather than assumed, and the per-frame variant
in §3 shows it is a property of the *fixed* reference, not of standardisation in general.

## 5. Which should be primary

* **Within a foam — raw px² s⁻¹ stays primary.** Period trends, horizon behaviour, the
  fragility ratios and the ground-truth comparison are all within-foam; K* multiplies them
  by a constant and adds a measured yardstick's uncertainty for no gain.
* **Across foams — report K* beside the raw value, and do not claim a magnification
  correction.** K* is the least-bad cross-foam summary because its yardstick is measured on
  the same detector and the same population as K itself, but §2 shows it is normalising by
  the foams' genuine fineness as much as by their optics.
* **No cross-foam magnitude claim should be made without saying which yardstick it uses.**
  The honest headline is that the foams' K values cannot be ranked without calibration.

## 6. Downstream statements that change if K* is adopted as the cross-foam primary

Unchanged (dimensionless or within-foam): **paper Figure 3** (fragility — every bar is a
ratio of K to K), **Figure 5** (neighbour counts), the ground-truth K comparison
(`+0.366` vs `+0.333`, same foam), all detector-effect ratios, and every period/horizon
*trend*.

Would change or need a stated yardstick:

| where | statement |
|---|---|
| `SUMMARY.md` §1 headline table | K values in px² s⁻¹; would gain a K* column |
| `SUMMARY.md` §1 gap decomposition | "Raw, Foam A looked 2.7× Foam C … at 600 s A and C agree to within 2%" — that is the D4 yardstick; under K* Foam C is 1.65× Foam A at 600 s |
| `SUMMARY.md` §1 | "The remaining difference is Foam F" |
| `SUMMARY.md` §5 | "Foam F is weak … 56 bubbles" (unchanged, but its K* interval is the widest by far: [1.25, 2.80]) |
| `SUMMARY.md` §7, `K_by_period.csv` | period tables in px² s⁻¹ |
| paper **Figure 1** | y-axis units px² s⁻¹; the shape is identical, a secondary s⁻¹ axis would serve |
| paper **Figure 2** | y-axis dA/dt in px² s⁻¹ (within-foam, unaffected in substance) |
| `METHODS_BRIEF.md` | "areas are px² and rates px²/s" — would need the K* definition and the A_char decision |
| `docs/cellpose_replication_v2.md` | the whole "replicates in form, differs in calibration" section, including "the detector accounts for 38–46%, the coarsening-rate normalisation 44–55%" |
| `tables/K_fits.csv`, `K_by_period.csv` | would gain K*, A_char columns |
| `colab_package/README.md:83` | **"Both share the same camera / magnification / image shape"** — contradicted: A is 2021 at JFIF 48 with a graph-paper ruler, C is 2026 at JFIF 60 with none, and their bubble/raft ratios differ 2.5× |

## 7. Limitations

* **A_char is measured with the same detector as K**, so detection error propagates into it.
  Foam F leaves ~27% of its raft interior unassigned and misses small rim bubbles, which
  biases its median detected area **up** and therefore its K* **down**; Foams C and F have
  no hand-labelled ground truth at all.
* **The raft proxy assumes comparable physical raft sizes.** That assumption is stated in
  §2 and cannot be checked from these images. The two dimensionless ratios need no such
  assumption and are the load-bearing evidence.
* **Bubbles per raft assumes comparable detection completeness** across foams, which is
  exactly what is unvalidated for C and F. A detector that missed half of Foam C's small
  bubbles would still leave it several times finer than Foam A, so the ordering is safe,
  but the factor of 5 is not exact.
* **Nothing here produces physical units.** Only the graph-paper pitch would, and only for
  Foam A.
