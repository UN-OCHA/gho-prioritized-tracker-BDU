# GHO 2026 Prioritized Tracker

**Maintained by:** OCHA Brand and Design Unit (BDU)
**Contact:** [ochavisual@un.org](mailto:ochavisual@un.org)
**Focal point:** Javier Cueto — [cuetoj@un.org](mailto:cuetoj@un.org)

## Purpose

Publishes an auto-updating CSV of the funding position of the **$23 billion prioritized
appeal** behind the **87 Million Lives campaign** (GHO 2026 Prioritized), for use in
Datawrapper charts on [unocha.org](https://www.unocha.org) and anywhere else the campaign
needs the official numbers as data.

## How it works

The figures are read straight from the **OCHA FTS Visualization Tool (PreCheck)** Power BI
dashboard — the same dashboard OCHA publishes and quotes from — via its public
`publish to web` endpoints. `update_data.py` replays the dashboard's own visual queries,
so the CSV matches the dashboard exactly. Nothing is recalculated here.

The people-in-need columns are not on the dashboard; those come from `people_data.csv` and
are joined on plan name.

A GitHub Action runs the script daily at 04:00 UTC and commits any change.

### Why it does not use the FTS API

It used to. Until September 2026 this script rebuilt the dashboard's methodology from
scratch — a hand-maintained prioritized-requirements list joined to plan-level funding
from `api.hpc.tools` — and it drifted:

| | requirements | funding | coverage |
|---|---|---|---|
| Old API-based method | $23.42bn | $12.27bn | 52.4% |
| Dashboard (official) | $24.94bn | $13.36bn | 53.5% |

The public API cannot close that gap. The dashboard attributes pooled-fund money back to
the original donor and strips regional-plan double counting, and OCHA revises the
prioritized requirements during the year. Maintaining a second implementation of that
methodology meant it was always going to fall behind. Reading the dashboard removes the
problem at the root.

### Failure behaviour

The script **fails loudly rather than publishing stale numbers.** It exits non-zero — so
the Action goes red and emails a maintainer — if the dashboard is unreachable, if a
figure comes back empty, or if the dashboard's own data date is more than 5 days old
(`--max-age-days`, or `MAX_DATA_AGE_DAYS`).

This matters: the first version of this repo had no workflow file at all despite the
README describing one, so it never ran, and the chart served 16 February 2026 figures
until September without anything appearing to be wrong.

## Output files

| File | Description | Updates |
|---|---|---|
| `output/gho_2026_prioritized_by_plan.csv` | Per plan: prioritized requirements, funding, coverage, people figures | Daily |
| `output/gho_2026_totals.csv` | Aggregate totals, plus the dashboard's data date and the run date | Daily |
| `output/_meta.json` | Provenance: data date, run time, plans with no people data | Daily |

Totals are taken from the dashboard's KPI cards rather than by summing the plan rows —
the cards already net out the regional-plan overlaps that individual rows still carry, so
the rows deliberately do not add up to the total.

## Datawrapper integration

Point the chart at the raw CSV URL:

```
https://raw.githubusercontent.com/UN-OCHA/gho-prioritized-tracker-BDU/main/output/gho_2026_prioritized_by_plan.csv
```

Datawrapper re-fetches on each page load, so the chart stays current automatically.

## Manual run

```bash
python update_data.py            # fetch and write
python update_data.py --dry-run  # print the totals, write nothing
```

Python 3.10+, standard library only — no `pip install` step.

## When it breaks

The read depends on three things inside the FTS report that can change if that team
rebuilds it:

1. **The cluster host** (`CLUSTER` in `ocha_fts_pbi.py`) — a wrong host returns 404. Open
   the dashboard in a browser and read the `wabi-*` entry from
   `performance.getEntriesByType('resource')`.
2. **The page name** (`PAGE_87_DAYS`) — this is the `pageName` in the dashboard's share URL.
3. **The visual ids** in `update_data.py` — a deleted and re-added visual gets a new id.
   `python ocha_fts_pbi.py <page>` lists the current ids with their titles.

## Data sources

- **Prioritized requirements and funding**: OCHA FTS Visualization Tool (PreCheck),
  GHO 2026 — 87 Million Lives campaign
- **People data**: GHO 2026 annual report dataset
  ([HDX](https://data.humdata.org/dataset/global-humanitarian-overview-2026))

## Repository

- **GitHub**: [UN-OCHA/gho-prioritized-tracker-BDU](https://github.com/UN-OCHA/gho-prioritized-tracker-BDU)
