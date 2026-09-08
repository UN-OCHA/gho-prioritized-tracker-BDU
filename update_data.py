#!/usr/bin/env python3
"""
GHO 2026 Prioritized Tracker — Data Updater

Reads the official figures out of the OCHA FTS Visualization Tool (PreCheck) Power BI
dashboard and writes them as CSV for Datawrapper.

Usage:
    python update_data.py                 # fetch and write
    python update_data.py --dry-run       # print the totals, write nothing
    python update_data.py --max-age-days 7

Output:
    output/gho_2026_prioritized_by_plan.csv
    output/gho_2026_totals.csv
    output/_meta.json

Why it reads the dashboard
--------------------------
Until September 2026 this script rebuilt the dashboard's methodology from scratch: a
hand-maintained prioritized-requirements list, joined to plain plan-level funding from
api.hpc.tools. Both halves drifted from the official figures — by Sept 2026 it reported
$23.42bn / $12.27bn / 52.4% where the dashboard said $24.94bn / $13.36bn / 53.5%. The
public FTS API cannot close that gap: the dashboard attributes pooled-fund money back to
the original donor and strips regional-plan double counting, and OCHA revises the
prioritized requirements over the year.

So the tracker no longer computes anything. It reads the dashboard's own visuals, which
makes the published CSV identical to the dashboard, the printed event dashboards, and
anything else quoting official campaign figures. There is no second implementation left
to go stale.

Staleness guard
---------------
The dashboard carries its own data date. If that date is older than --max-age-days, this
script exits non-zero so the GitHub Action fails and emails a maintainer, rather than
quietly republishing yesterday's numbers forever. That silent-staleness failure is
exactly what left this chart frozen at 16 February 2026 for seven months.

No dependencies beyond the Python 3.10+ standard library.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timezone

import ocha_fts_pbi as pbi

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
PEOPLE_CSV = os.path.join(SCRIPT_DIR, "people_data.csv")

# Visuals on the dashboard's "OnePager (87 Days)" page. If the FTS team rebuilds the
# report these ids change; `python ocha_fts_pbi.py <page>` lists the current ones.
VISUAL_PLANS = "c056db16e838338ec71e"  # "By GHO Plans (in USD)"
VISUAL_DATA_DATE = "c299af827dcd82be601b"  # "FTS API checksum date"
KPI_VISUALS = {
    "prioritized_requirements_usd": "8f7f2025c2d3027462de",
    "prioritized_funding_usd": "0c2709702536cf493508",
    "prioritized_coverage": "3e367e8735f8a5076eae",
    "total_gho_requirements_usd": "7e26019a41ee238e4a04",
    "total_gho_funding_usd": "0fbfef691b05063628bd",
}

# The dashboard names plans in full, and in French or Spanish where that is the plan's
# own name. people_data.csv keys them by short English country name.
_PLAN_NOISE = re.compile(
    r"\s*(humanitarian needs and response plan|besoins humanitaires et plan de réponse|"
    r"necesidades humanitarias y plan de respuesta|plan de respuesta humanitaria|"
    r"humanitarian response plan|regional refugee response plan|refugee response plan|"
    r"flash appeal|regional migrant response plan)\s*",
    re.IGNORECASE,
)
_PEOPLE_KEY_ALIASES = {
    "république démocratique du congo": "Democratic Republic of the Congo",
    "république centrafricaine": "Central African Republic",
    "tchad": "Chad",
    "escalation of hostilities in the opt": "Occupied Palestinian Territory",
    "sudan emergency:": "Sudan",
    "syrian arab republic regional refugee and resilience plan (3rp)": "Syria (3RP)",
    "rohingya humanitarian crisis joint response plan": "Rohingya (JRP)",
    "venezuela regional refugee and migrant response plan (rmrp)": "Venezuela (RMRP)",
    "for horn of africa to yemen and southern africa": "Horn of Africa to Yemen and Southern Africa (MRP)",
}

FIELDNAMES = [
    "Plan",
    "Plan Type",
    "Prioritized Requirements (USD)",
    "Funding received (USD)",
    "Unfunded (USD)",
    "Coverage (%)",
    "Full Requirements (USD)",
    "People in Need",
    "People Targeted",
    "People Prioritized",
]


def short_plan_name(full_name: str) -> str:
    name = _PLAN_NOISE.sub(" ", full_name or "")
    name = re.sub(r"\b20\d\d\b", "", name)
    return re.sub(r"\s+", " ", name).strip(" -–—")


def people_key(short_name: str) -> str:
    key = short_name.strip().lower()
    return _PEOPLE_KEY_ALIASES.get(key, short_name).strip().lower()


def load_people() -> dict[str, dict]:
    if not os.path.exists(PEOPLE_CSV):
        return {}
    with open(PEOPLE_CSV, newline="") as fh:
        return {row["plan"].strip().lower(): row for row in csv.DictReader(fh)}


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def first_value(rows: list[dict]):
    """Cards and gauges return a single row holding a single measure."""
    for row in rows:
        for value in row.values():
            if value is not None:
                return pbi.to_number(value)
    return None


def check_freshness(data_date: str | None, max_age_days: int) -> None:
    """Refuse to publish if the dashboard itself has stopped moving."""
    if not data_date:
        raise SystemExit("ABORT: the dashboard did not report a data date — refusing to publish.")
    try:
        parsed = datetime.strptime(str(data_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit(f"ABORT: could not read the dashboard's data date {data_date!r}.")
    age = (date.today() - parsed).days
    if age > max_age_days:
        raise SystemExit(
            f"ABORT: the dashboard's data is {age} days old (dated {parsed}, limit "
            f"{max_age_days}). Not republishing stale figures — check whether the FTS "
            f"dashboard has stopped refreshing."
        )
    print(f"Dashboard data date: {parsed} ({age} day(s) old)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print the totals, write nothing")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=int(os.environ.get("MAX_DATA_AGE_DAYS", 5)),
        help="fail if the dashboard's own data is older than this (default 5)",
    )
    args = parser.parse_args()

    run_at = datetime.now(timezone.utc)
    print(f"[{run_at:%Y-%m-%d %H:%M UTC}] Reading the FTS dashboard...")

    model = pbi.fetch_model()
    page = pbi.PAGE_87_DAYS

    data_date = first_value(pbi.run_visual(model, page, VISUAL_DATA_DATE))
    check_freshness(data_date, args.max_age_days)

    kpis = {
        name: first_value(pbi.run_visual(model, page, visual_id))
        for name, visual_id in KPI_VISUALS.items()
    }
    missing = [name for name, value in kpis.items() if value is None]
    if missing:
        raise SystemExit(f"ABORT: the dashboard returned no value for {', '.join(missing)}.")

    plans = pbi.run_visual(model, page, VISUAL_PLANS)
    people = load_people()

    rows = []
    for plan in plans:
        full_name = plan.get("Plan Name")
        if not full_name:
            continue  # grouping header row, not a plan
        name = short_plan_name(full_name)
        required = pbi.to_number(plan.get("GHO Required (Prioritized)*")) or 0
        funding = pbi.to_number(plan.get("GHO Funding (Prioritized)")) or 0
        coverage = pbi.to_number(plan.get("GHO Coverage (Prioritized)")) or 0
        match = people.get(people_key(name), {})
        rows.append(
            {
                "Plan": name,
                "Plan Type": plan.get("Plan type") or "",
                "Prioritized Requirements (USD)": round(required),
                "Funding received (USD)": round(funding),
                "Unfunded (USD)": round(max(0, required - funding)),
                "Coverage (%)": round(coverage * 100, 1),
                "Full Requirements (USD)": match.get("full_requirements", ""),
                "People in Need": match.get("people_in_need", ""),
                "People Targeted": match.get("people_targeted", ""),
                "People Prioritized": match.get("people_prioritized", ""),
            }
        )

    if not rows:
        raise SystemExit("ABORT: the dashboard returned no plan rows.")
    rows.sort(key=lambda r: r["Prioritized Requirements (USD)"], reverse=True)

    # Totals come from the dashboard's KPI cards, not from summing the rows above: the
    # cards already net out the regional-plan overlaps that individual rows still carry.
    totals = [
        {"Metric": "Prioritized Requirements (total)", "Value": round(kpis["prioritized_requirements_usd"])},
        {"Metric": "Funding (total)", "Value": round(kpis["prioritized_funding_usd"])},
        {"Metric": "Percentage", "Value": round(kpis["prioritized_coverage"] * 100, 1)},
        {"Metric": "Data as of", "Value": str(data_date)[:10]},
        {"Metric": "Last Updated", "Value": f"{run_at:%Y-%m-%d}"},
    ]

    no_people = [r["Plan"] for r in rows if not r["People in Need"]]
    print(f"Plans:                {len(rows)}")
    print(f"Prioritized Reqs:     ${kpis['prioritized_requirements_usd'] / 1e9:.2f}bn")
    print(f"Funding:              ${kpis['prioritized_funding_usd'] / 1e9:.2f}bn")
    print(f"Coverage:             {kpis['prioritized_coverage'] * 100:.1f}%")
    if no_people:
        print(f"No people data for {len(no_people)}: {', '.join(no_people)}")

    if args.dry_run:
        print("Dry run — nothing written.")
        return 0

    by_plan_path = os.path.join(OUTPUT_DIR, "gho_2026_prioritized_by_plan.csv")
    totals_path = os.path.join(OUTPUT_DIR, "gho_2026_totals.csv")
    write_csv(by_plan_path, rows, FIELDNAMES)
    write_csv(totals_path, totals, ["Metric", "Value"])

    with open(os.path.join(OUTPUT_DIR, "_meta.json"), "w") as fh:
        json.dump(
            {
                "source": "OCHA FTS Visualization Tool (PreCheck), Power BI publish-to-web",
                "dashboard_data_date": str(data_date)[:10],
                "generated_at": f"{run_at:%Y-%m-%d %H:%M UTC}",
                "plans": len(rows),
                "plans_without_people_data": no_people,
                "totals": {name: kpis[name] for name in sorted(kpis)},
            },
            fh,
            indent=2,
        )

    print(f"Output:               {by_plan_path}")
    print(f"                      {totals_path}")
    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except pbi.PowerBIError as exc:
        # A failed read must stop the run. Publishing the previous CSV unchanged would
        # look like "no change today" instead of "the dashboard is unreachable".
        raise SystemExit(f"ABORT: could not read the FTS dashboard — {exc}")
