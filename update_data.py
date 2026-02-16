#!/usr/bin/env python3
"""
GHO 2026 Prioritized Tracker — Data Updater

Fetches live funding data from the FTS API (api.hpc.tools) and merges it
with the static prioritized requirements to produce a CSV for Datawrapper.

Usage:
    python update_data.py

Output:
    output/gho_2026_prioritized_by_plan.csv
    output/gho_2026_prioritized_by_sector.csv
    output/gho_2026_totals.csv
"""

import csv
import json
import os
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_URL = "https://api.hpc.tools/v2/public/plan/overview/2026"
FLOW_URL = "https://api.hpc.tools/v1/public/fts/flow?year=2026&groupby=plan"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRIORITIZED_CSV = os.path.join(SCRIPT_DIR, "prioritized_requirements.csv")
PEOPLE_CSV = os.path.join(SCRIPT_DIR, "people_data.csv")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

# Map spreadsheet plan names → API shortName (only where they differ)
NAME_TO_API = {
    "Democratic Republic of the Congo": "DRC",
    "Occupied Palestinian Territory": "oPt",
    "Syrian Arab Republic": "Syria",
    "Sudan (RRP)": "Sudan (RRP)",
    "Horn of Africa to Yemen and Southern Africa (MRP)": "Horn of Africa",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fetch_json(url: str) -> dict:
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "GHO-Tracker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def load_csv_map(path: str, key_col: str) -> dict:
    """Load a CSV into a dict keyed by key_col."""
    with open(path, newline="") as f:
        return {row[key_col].strip(): row for row in csv.DictReader(f)}


def write_csv(path: str, rows: list[dict], fieldnames: list[str]):
    """Write a list of dicts to CSV."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def match_api_plan(name: str, api_plans: dict) -> dict | None:
    """Find the matching API plan for a spreadsheet plan name."""
    # Direct match
    if name in api_plans:
        return api_plans[name]

    # Mapped name
    mapped = NAME_TO_API.get(name)
    if mapped and mapped in api_plans:
        return api_plans[mapped]

    # Fuzzy: check if spreadsheet name is contained in API full name
    for short, plan in api_plans.items():
        if name.lower() in plan["fullName"].lower():
            return plan
        # Match first word (e.g. "Uganda" matches "Uganda (RRP)")
        if name.split("(")[0].strip().lower() == short.split("(")[0].strip().lower():
            return plan

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] Fetching FTS API data...")

    # 1. Fetch live data from API
    overview = fetch_json(API_URL)
    flow_data = fetch_json(FLOW_URL)

    # 2. Build API plan lookup (GHO plans only)
    api_plans = {}
    for p in overview["data"]["plans"]:
        if not p.get("isPartOfGHO"):
            continue
        short = (p.get("shortName") or p["name"]).strip()
        api_plans[short] = {
            "fullName": p["name"],
            "funding": p.get("funding", {}).get("totalFunding", 0),
            "totalReqs": p.get("requirements", {}).get("revisedRequirements", 0),
            "progress": p.get("funding", {}).get("progress", 0),
            "planType": p.get("planType", {}).get("code", ""),
            "planId": p["id"],
        }

    # 3. Build pledges lookup from flow data
    pledges_by_plan = {}
    if "data" in flow_data and "report2" in flow_data["data"]:
        pledge_totals = flow_data["data"].get("pledgeTotals", {})
        for obj in pledge_totals.get("objects", []):
            for item in obj.get("singleFundingObjects", []):
                pledges_by_plan[item.get("name", "")] = item.get("totalFunding", 0)

    # 4. Load static prioritized requirements
    pri_map = load_csv_map(PRIORITIZED_CSV, "plan")
    people_map = load_csv_map(PEOPLE_CSV, "plan")

    # 5. Merge: prioritized reqs (static) + funding (live)
    rows = []
    total_pri = 0
    total_funding = 0
    total_unfunded = 0

    for name, pri_row in pri_map.items():
        pri_req = int(pri_row["prioritized_requirements"])
        if pri_req <= 0:
            continue  # skip Niger (0) and overlaps

        api = match_api_plan(name, api_plans)
        funding = api["funding"] if api else 0
        full_reqs = api["totalReqs"] if api else 0
        plan_type = api["planType"] if api else ""
        coverage = round(funding / pri_req * 100, 1) if pri_req > 0 else 0
        unfunded = max(0, pri_req - funding)

        # People data
        pp = people_map.get(name, {})

        rows.append({
            "Plan": name,
            "Plan Type": plan_type,
            "Prioritized Requirements (USD)": pri_req,
            "Funding received (USD)": round(funding),
            "Unfunded (USD)": round(unfunded),
            "Coverage (%)": coverage,
            "Full Requirements (USD)": round(full_reqs),
            "People in Need": pp.get("people_in_need", ""),
            "People Targeted": pp.get("people_targeted", ""),
            "People Prioritized": pp.get("people_prioritized", ""),
        })

        total_pri += pri_req
        total_funding += funding
        total_unfunded += unfunded

    # Sort by prioritized requirements descending
    rows.sort(key=lambda r: r["Prioritized Requirements (USD)"], reverse=True)

    # 6. Apply overlap adjustments to totals
    # (Horn of Africa overlap: -19138004, Sudan RRP overlap: -575662771)
    overlap_hor = -19138004
    overlap_sudan = -575662771
    total_pri_adjusted = total_pri + overlap_hor + overlap_sudan

    # 6b. Add totals row
    total_coverage = round(total_funding / total_pri_adjusted * 100, 1) if total_pri_adjusted > 0 else 0
    rows.append({
        "Plan": "Total",
        "Plan Type": "",
        "Prioritized Requirements (USD)": round(total_pri_adjusted),
        "Funding received (USD)": round(total_funding),
        "Unfunded (USD)": round(max(0, total_pri_adjusted - total_funding)),
        "Coverage (%)": total_coverage,
        "Full Requirements (USD)": "",
        "People in Need": "",
        "People Targeted": "",
        "People Prioritized": "",
    })

    # 7. Write by-plan CSV
    fieldnames = [
        "Plan", "Plan Type",
        "Prioritized Requirements (USD)", "Funding received (USD)",
        "Unfunded (USD)", "Coverage (%)",
        "Full Requirements (USD)",
        "People in Need", "People Targeted", "People Prioritized",
    ]
    by_plan_path = os.path.join(OUTPUT_DIR, "gho_2026_prioritized_by_plan.csv")
    write_csv(by_plan_path, rows, fieldnames)

    # 8. Write totals CSV
    totals_rows = [{
        "Metric": "Prioritized Requirements (USD)",
        "Value": round(total_pri_adjusted),
    }, {
        "Metric": "Funding received (USD)",
        "Value": round(total_funding),
    }, {
        "Metric": "Unfunded (USD)",
        "Value": round(max(0, total_pri_adjusted - total_funding)),
    }, {
        "Metric": "Coverage (%)",
        "Value": total_coverage,
    }, {
        "Metric": "Plans Count",
        "Value": len(rows) - 1,  # exclude totals row
    }, {
        "Metric": "Last Updated",
        "Value": now,
    }]
    totals_path = os.path.join(OUTPUT_DIR, "gho_2026_totals.csv")
    write_csv(totals_path, totals_rows, ["Metric", "Value"])

    # 9. Print summary
    print(f"Plans:                {len(rows)}")
    print(f"Prioritized Reqs:     ${total_pri_adjusted / 1e9:.2f}bn")
    print(f"Funding:              ${total_funding / 1e9:.2f}bn")
    print(f"Coverage:             {total_coverage}%")
    print(f"Output:               {by_plan_path}")
    print(f"                      {totals_path}")
    print(f"Done.")


if __name__ == "__main__":
    main()
