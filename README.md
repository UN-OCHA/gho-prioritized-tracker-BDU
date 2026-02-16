# GHO 2026 Prioritized Tracker

Auto-updating dataset that merges **static prioritized requirements** (from OCHA's GHO 2026) with **live funding data** from the [FTS API](https://api.hpc.tools), producing CSVs ready for [Datawrapper](https://www.datawrapper.de/).

## Output files

| File | Description | Updates |
|---|---|---|
| `output/gho_2026_prioritized_by_plan.csv` | 26 plans with prioritized reqs, live funding, coverage | Daily via GitHub Actions |
| `output/gho_2026_totals.csv` | Aggregate totals (requirements, funding, coverage) | Daily via GitHub Actions |

## How it works

1. **Prioritized requirements** (`prioritized_requirements.csv`) — static data from OCHA's GHO 2026 prioritization. Update manually when OCHA revises priorities.
2. **Live funding** — fetched daily from `api.hpc.tools/v2/public/plan/overview/2026` (FTS updates at 02:00 CET).
3. **Merge** — `update_data.py` joins both sources, calculates coverage, and writes CSVs.
4. **GitHub Actions** runs the script daily at 04:00 UTC and commits any changes.

## Datawrapper setup

1. In Datawrapper, create a new chart
2. Under **Data** → **Link external dataset**
3. Use the **raw GitHub URL** for the CSV you want:
   ```
   https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/output/gho_2026_prioritized_by_plan.csv
   ```
4. Datawrapper will re-fetch the CSV on each page load, so your chart stays current

## Data sources

- **Prioritized requirements**: OCHA GHO 2026 (87 Million Lives campaign)
- **Live funding**: [FTS Public API](https://fts.unocha.org/content/fts-public-api) via `api.hpc.tools`
- **People data**: GHO 2026 annual report dataset

## Manual run

```bash
python update_data.py
```

No dependencies beyond Python 3.10+ standard library.
