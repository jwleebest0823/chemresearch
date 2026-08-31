# Topological event prediction — STOPPED AT THE LABEL GATE

**Verdict: the event labels are not trustworthy enough to train on, and no classifier was
built.** The brief pre-authorised this outcome ("If event labels are still unreliable, say
so and stop — do not build a classifier on noisy labels"), and the measurements say to
take it. Three independent things block the session, any one of which would be sufficient.

## Task 1 — label reliability, the gate

`# DECISION` — thresholds registered **before** running, and tied to existing project
constants rather than chosen from the output: a session's labels are USABLE only if
(a) births are < 25% of the frame-0 population, and (b) the median lifetime of the
bubbles that die exceeds `StabilityConfig.min_persist_frames` (5). Both are properties of
the identity stream alone.

### Event counts

| session | foam | frames | n₀ → n_T | T2 | merge | **T1** | birth | events/frame |
|---|---|---|---|---|---|---|---|---|
| exp1_run0 | A | 99 | 118 → 61 | 72 | 23 | **0** | 22 | 1.18 |
| exp1_run1 | A | 99 | 60 → 28 | 41 | 2 | **1** | 12 | 0.57 |
| exp3_cellpose | C | 99 | 555 → 221 | 918 | 68 | **1** | 632 | 16.35 |
| exp10_w | F | 226 | 62 → 20 | 305 | 8 | **0** | 271 | 2.58 |

### The flicker signature — a coarsening foam cannot gain bubbles

| session | births | / frame-0 pop. | deaths per birth | median lifetime of dying | % dying ≤ 3 frames | **verdict** |
|---|---|---|---|---|---|---|
| exp1_run0 | 22 | 18.6% | 4.32 | **15.0** | 25.3% | **USABLE** |
| exp1_run1 | 12 | 20.0% | 3.58 | **23.0** | 25.0% | **USABLE** |
| exp3_cellpose | 632 | **113.9%** | **1.56** | **2.0** | 58.5% | **REJECT** |
| exp10_w | 271 | **437.1%** | **1.15** | **2.0** | 58.5% | **REJECT** |

**Foam C mints more new identities than it started with, and Foam F mints four times its
starting population.** In both, the median bubble that "dies" lived **2 frames** and
deaths barely outnumber births (1.15–1.56 : 1). That is the churn signature the brief
asked me to check for, and it is emphatically still present on two of the three foams. A
"T2 death" in that regime is overwhelmingly a detector flicker wearing an ID, not a
bubble leaving the foam.

Foam A is genuinely better: deaths outnumber births 3.6–4.3 : 1 and the median dying
bubble lived 15–23 frames. Its labels pass. But ~25% of its dying bubbles still live ≤ 3
frames, so even Foam A's death labels carry a ~1-in-4 contamination floor.

### The finding that matters beyond this session

**A clean region-count curve does not imply a clean identity stream.** All three foams
pass the fragmentation guard and coarsen monotonically (ρ = −0.995 to −0.9993) — that is
what got them accepted in `docs/cellpose_replication_v2.md`. But the guard counts *how
many* bubbles exist, never *whether they are the same bubbles*. Foam F falls 62 → 20 with
ρ = −0.995 while minting 271 new identities underneath. Any future claim that rests on
identity — events, lifetimes, genealogies, per-bubble trajectories — needs the
births/lifetime check above, not just the count guard.

**This does not retract the K results.** The trusted-track filter (`min_persist_frames`,
no gaps, no merges, dropout-recovery) exists precisely to remove churned tracks, and it
does: Foam C keeps 466 of 1187 tracks, discarding 60%. K is fitted on the survivors. What
fails here is the *event* layer, which by construction cannot be filtered the same way —
an event **is** the identity discontinuity the filter throws away.

## Task 2 — why no formulation survives

Even confining everything to Foam A, the only foam that passed:

| candidate formulation (from the brief) | usable labels on Foam A | status |
|---|---|---|
| **Edge-level rupture** (T1 neighbour swaps) | **1** | dead — no labels |
| **Coalescence partner** (merges) | **25** | dead — too few, and one foam only |
| Node-level survival (all deaths) | 138 | only viable count, but see below |

Three blocks, independently fatal:

1. **Leave-one-foam-out is impossible.** One usable foam. `exp1_run0` and `exp1_run1` are
   two *sessions of the same physical raft*, not two foams — the project has treated that
   distinction as load-bearing since `dataset.py` was written, and relaxing it here to
   manufacture a second "fold" would be exactly the leakage that invalidated the original
   t+20 GNN result.
2. **The most relational target has no data.** T1 swaps are the canonical relational
   event — an edge lost and another gained among four mutually adjacent bubbles — and
   there is **1 of them in 198 Foam A frames** (2 across all four sessions). The
   formulation the brief correctly identified as "the most explicitly relational" cannot
   be attempted at all.
3. **The one target with enough labels is the least relational.** Node-level survival has
   138 events, but "will this bubble disappear" is plausibly determined by its own area
   and `n_sides` — the same structural redundancy that made the dA/dt task
   uninformative about topology. Winning there would not be evidence that topology helps;
   losing there would not be evidence that it doesn't.

So the one target where topology is theoretically necessary has no labels, and the one
target with labels is the one where topology is theoretically redundant.

## Task 3/4 — not run, deliberately

No models were trained. Training a GNN on 25 coalescence events from a single foam with
no possible held-out foam would produce a number, and that number would be
uninterpretable — which is the failure mode this project has spent several sessions
removing rather than adding.

The pre-committed interpretations in the brief all presuppose a valid comparison; none
applies. The honest fourth outcome is the one that obtains: **the experiment could not be
run on this data.**

## Visual audit — and its limitation, which I ran into

`qc/events/audit_exp1_run0.png` (passed the gate) and `qc/events/audit_exp3_cellpose.png`
(failed it) overlay 6 sampled death events each on the real consecutive frames, dying
bubble in red.

**Honest reading of them: both look plausible, including Foam C's.** Foam A's sampled
events are clean — small bubbles present at *t*, absent at *t+1*, in a well-segmented
raft. But Foam C's sampled events look much the same: small bubbles vanishing between
consecutive frames, which is what a genuine T2 looks like.

That is a limitation of the audit as built, not a contradiction of the gate. **Showing
only *t* and *t+1* cannot distinguish a genuine death from a one-frame dropout** — a
flicker and a real disappearance are identical over two frames and differ only at *t+2*,
when the flicker comes back. The quantitative evidence is what separates them, and it
does so decisively: a foam whose dying bubbles have a **median lifetime of 2 frames** and
which mints **632 new identities**, has bubbles being re-detected under new IDs, whatever
any two-frame crop looks like.

`# DECISION` — I am reporting the images as inconclusive rather than as corroboration.
Extending the audit to *t−1 … t+3* would make flicker directly visible and is the cheap
next step for anyone revisiting this; it was not done here because the lifetime statistic
had already settled the gate.

## What would unblock this

In rough order of leverage:

1. **Identity, not detection, is now the binding constraint.** Detection is solved
   (F1 0.9664, ⟨n⟩ matching GT to +0.03); the tracker is what mints 632 IDs on Foam C.
   A tracker that exploits Cellpose's per-frame quality — e.g. matching on mask IoU with
   a proper assignment rather than the current overlap heuristic, or a learned
   re-identification step — is the prerequisite for every identity-dependent question.
2. **More foams with clean identities.** LOFO needs ≥ 2. Foam A alone can never support a
   cross-foam claim regardless of how good its labels are.
3. **T1 detection may itself be too strict.** Finding 2 swaps in 500+ frames of coarsening
   foam is suspicious on its own — real 2D foams undergo T1s routinely. Before concluding
   T1s are absent, `_detect_t1_between`'s requirement (all four bubbles persisting, both
   the lost and gained edges clearing `min_shared_border_px`) should be checked against
   hand-identified swaps. That is a separate, cheap investigation and it is a genuine
   open question, not a workaround.

**GT masks untouched — SHA-256 verified.** Artifacts: `qc/events/`. Driver:
`dev/events_extract.py`, audit `dev/events_audit_overlay.py`.
