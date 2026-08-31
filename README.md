# chemresearch

Two independent projects share this repository. They have no code in common and are
built and run separately.

| | What it is | Stack | Directory |
|---|---|---|---|
| **Alabama Environmental Monitoring Dashboard** | Community-facing web app for Alabama air/water quality, industrial emissions and EPA violation records | Vite + React 18 + TypeScript + Tailwind + Supabase | repository root (`src/`, `supabase/`) |
| **foam_gnn** | Physics-informed research pipeline for quasi-2D soap-foam coarsening (segmentation → tracking → graph → modelling) | Python 3, self-contained | [`foam_gnn/`](foam_gnn/) |

`foam_gnn/` is deliberately self-contained — its own dependencies, tests and packaging —
and can be lifted into a standalone repository without changes.

---

## 1. Alabama Environmental Monitoring Dashboard

A dashboard that pulls environmental monitoring data into one place for Alabama
residents, with a path for the public to submit their own observations.

**Tabs** (`src/components/tabs/`): Overview · Monitoring · Violations · Community ·
Data Guide · Admin.
**Topic modules** (`src/components/modules/`): `CarbonSinkAL`, `CokeWatch`, `PFASCheck`.

State is held in a Zustand store (`src/store/`); Supabase provides the database and the
schema lives in `supabase/migrations/`.

### Setup

Requires Node.js 20+.

```bash
npm install
```

Create a `.env` file in the repository root — the Supabase client throws on startup if
either variable is missing (`src/lib/supabase.ts`):

```
VITE_SUPABASE_URL=<your-project-url>
VITE_SUPABASE_ANON_KEY=<your-anon-key>
```

`.env` is gitignored. Never commit real keys.

### Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run typecheck` | `tsc --noEmit` (TypeScript strict mode is on) |
| `npm run lint` | ESLint |

### Database

Migrations in `supabase/migrations/` are ordered by their timestamp prefix and cover the
curriculum/admin tables, curriculum box mappings, sample environmental data, and the
detailed community-reports schema. Apply them with the Supabase CLI or the dashboard SQL
editor.

---

## 2. foam_gnn

Physics-informed graph-neural-network pipeline for a **quasi-2D evaporating soap foam**
imaged by brightfield microscopy. It measures whether **von Neumann's law**
(`dA/dt = K(n − 6)`) holds in this system, and how much of any apparent failure is
measurement artifact rather than physics.

**Headline result:** von Neumann's law holds on all three usable foams under a single
detector, with K positive and its confidence interval clear of zero in all nine
foam × horizon cells. Five separate measurement artifacts had previously faked its
failure — one of them producing a large *negative* K.

Full detail, with every number traced to a table or figure:

- [`foam_gnn/results_package/SUMMARY.md`](foam_gnn/results_package/SUMMARY.md) — main results
- [`foam_gnn/results_package_extra/T1_ADDENDUM.md`](foam_gnn/results_package_extra/T1_ADDENDUM.md) — neighbour-swap (T1) follow-up
- [`foam_gnn/README.md`](foam_gnn/README.md) — dataset structure, install, module status
- [`foam_gnn/docs/`](foam_gnn/docs/) — the running lab notebook, including retracted and
  negative results (kept deliberately: they are the audit trail for the corrections above)

### Setup

```bash
cd foam_gnn
pip install -e .          # base pipeline, no deep-learning stack
pip install -e ".[ml]"    # adds the model/training stack
pytest                    # real-data tests skip when data/ is absent
```

Raw microscopy data is **not** in this repository (gitignored). The five sample frames
under `foam_gnn/tests/fixtures/samples/` are committed on purpose for smoke tests, and
the hand-corrected ground-truth labels under `foam_gnn/groundtruth/` are committed as
research artifacts.

---

## Contributing

This is the **canonical** repository. It carries the full history of the earlier
`jwleebest0823/chemresearch`, which is kept for reference only.

Clone this repository directly, branch, and open a PR against `main`. To bring work over
from the legacy repository — including after it is archived — see
[`SYNCING.md`](SYNCING.md).

## Repository conventions

- Code comments and commit messages in English; Conventional Commits (`feat:`, `fix:`,
  `docs:`, `refactor:`, `chore:`).
- Secrets only via environment variables — never hardcoded, never committed.
- `foam_gnn` fails loud by design: bad shapes, dtypes or NaNs raise immediately rather
  than silently producing garbage.
