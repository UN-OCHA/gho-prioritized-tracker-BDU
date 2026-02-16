# GHO 2026 Prioritized Tracker

**Maintained by:** OCHA Brand and Design Unit (BDU)
**Contact:** [ochavisual@un.org](mailto:ochavisual@un.org)
**Focal point:** Javier Cueto — [cuetoj@un.org](mailto:cuetoj@un.org)

## Purpose

This repo produces an auto-updating CSV that feeds a **Datawrapper chart** visualizing the funding tracking of the **$23 billion appeal** for the **87 Million Lives campaign** (GHO 2026 Prioritized).

The chart is published on [unocha.org](https://www.unocha.org).

## How it works

1. **Prioritized requirements** (`prioritized_requirements.csv`) — static data from OCHA's GHO 2026 prioritization targeting 87 million people. Update manually when OCHA revises priorities.
2. **Live funding** — fetched daily from the [FTS Public API](https://fts.unocha.org/content/fts-public-api) at `api.hpc.tools/v2/public/plan/overview/2026`. FTS data updates at 02:00 CET.
3. **Merge** — `update_data.py` joins both sources, calculates coverage per plan, and writes CSVs.
4. **GitHub Actions** runs the script daily at 04:00 UTC and commits any changes.

## Output files

| File | Description | Updates |
|---|---|---|
| `output/gho_2026_prioritized_by_plan.csv` | 26 plans with prioritized reqs, live funding, coverage | Daily via GitHub Actions |
| `output/gho_2026_totals.csv` | Aggregate totals (requirements, funding, coverage) | Daily via GitHub Actions |

## Datawrapper integration

The Datawrapper chart links to the raw CSV URL:

```
https://raw.githubusercontent.com/UN-OCHA/gho-prioritized-tracker-BDU/main/output/gho_2026_prioritized_by_plan.csv
```

Datawrapper re-fetches the CSV on each page load, so the chart stays current automatically.

## Data sources

- **Prioritized requirements**: OCHA GHO 2026 — 87 Million Lives campaign ($23B prioritized subset of the full $33B GHO appeal)
- **Live funding**: [FTS Public API](https://api.hpc.tools/v2/public/plan/overview/2026) via `api.hpc.tools`
- **People data**: GHO 2026 annual report dataset ([HDX](https://data.humdata.org/dataset/global-humanitarian-overview-2026))

## Manual run

```bash
python update_data.py
```

No dependencies beyond Python 3.10+ standard library.

## Repository

- **GitHub**: [UN-OCHA/gho-prioritized-tracker-BDU](https://github.com/UN-OCHA/gho-prioritized-tracker-BDU)
