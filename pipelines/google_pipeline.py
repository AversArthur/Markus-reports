"""
Google Ads pipeline via Windsor.ai.

Fetches yesterday's data from Windsor.ai and appends one row to
data/{client_id}/google.json.

Required env vars:
  WINDSOR_API_KEY  – found in Windsor.ai dashboard → Settings → API

Install:
  pip install requests python-dotenv
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

WINDSOR_API_KEY = os.environ["WINDSOR_API_KEY"]
WINDSOR_BASE = "https://connectors.windsor.ai/google_ads"

# ---------------------------------------------------------------------------
# Config: map client IDs to one or more Google Ads account IDs.
# Use a list when one client has multiple ad accounts (they will be summed).
# ---------------------------------------------------------------------------
CLIENTS = {
    "vogelschutz": ["537-317-1947"],
    # Add other clients when their Google Ads accounts are connected:
    # "famev":                 ["XXX-XXX-XXXX"],
    # "fruchtalarm":           ["XXX-XXX-XXXX"],
    # "reporter_ohne_grenzen": ["XXX-XXX-XXXX"],
    # "rettungshunde":         ["XXX-XXX-XXXX"],
    # "sound_of_peace":        ["XXX-XXX-XXXX"],
}

FIELDS = [
    "date", "spend", "clicks", "impressions", "all_conversions",
]

YESTERDAY = date.today() - timedelta(days=1)


def fetch_one_account(account_id: str, day: date) -> dict:
    params = {
        "api_key": WINDSOR_API_KEY,
        "date_from": str(day),
        "date_to": str(day),
        "fields": ",".join(FIELDS),
        "account_id": account_id,
    }
    resp = requests.get(WINDSOR_BASE, params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    return {
        "spend":  sum(float(r.get("spend", 0) or 0) for r in rows),
        "clicks": sum(int(r.get("clicks", 0) or 0) for r in rows),
        "imp":    sum(int(r.get("impressions", 0) or 0) for r in rows),
        "donors": sum(int(r.get("all_conversions", 0) or 0) for r in rows),
    }


def fetch_day(account_ids: list, day: date) -> dict:
    totals = {"spend": 0.0, "clicks": 0, "imp": 0, "donors": 0}
    for aid in account_ids:
        result = fetch_one_account(aid, day)
        for k in totals:
            totals[k] += result[k]
    donors = totals["donors"]
    return {
        "date":     str(day),
        "spend":    round(totals["spend"], 2),
        "donors":   donors,
        "rec":      0,
        "einzel":   donors,
        "imp":      totals["imp"],
        "clicks":   totals["clicks"],
        "lpvisits": totals["clicks"],
    }


def run():
    data_root = Path(__file__).parent.parent / "data"

    for client_id, account_ids in CLIENTS.items():
        if isinstance(account_ids, str):
            account_ids = [account_ids]

        path = data_root / client_id / "google.json"
        if path.exists():
            existing = json.loads(path.read_text())
        else:
            existing = {"updated": "", "rows": []}

        existing_dates = {r["date"] for r in existing["rows"]}
        if str(YESTERDAY) in existing_dates:
            print(f"  {client_id}: {YESTERDAY} already present, skipping")
            continue

        accs = ", ".join(account_ids)
        print(f"Fetching Google Ads for {client_id} [{accs}] / {YESTERDAY}...")
        row = fetch_day(account_ids, YESTERDAY)

        existing["rows"].append(row)
        existing["rows"].sort(key=lambda r: r["date"])
        existing["updated"] = str(date.today())

        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        s, d, c = row["spend"], row["donors"], row["clicks"]
        print(f"  spend={s} donors={d} clicks={c}")
        print(f"  → Appended to {path}")


if __name__ == "__main__":
    run()
