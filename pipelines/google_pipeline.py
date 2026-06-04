"""
Google Ads pipeline via Windsor.ai.

Fetches yesterday's data from Windsor.ai (all accounts in one request)
and appends one row per client to data/{client_id}/google.json.

Required env vars:
  WINDSOR_API_KEY  – Windsor.ai Settings → API

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
# Config: map client IDs to Google Ads account IDs.
# Data is fetched in one request and split client-side by account_id.
# ---------------------------------------------------------------------------
CLIENTS = {
    "vogelschutz": "537-317-1947",
    "vsk": "291-201-3794",
    # Add other clients when their Google Ads accounts are connected:
    # "famev":                 "XXX-XXX-XXXX",
    # "fruchtalarm":           "XXX-XXX-XXXX",
    # "reporter_ohne_grenzen": "XXX-XXX-XXXX",
    # "rettungshunde":         "XXX-XXX-XXXX",
    # "sound_of_peace":        "XXX-XXX-XXXX",
}

FIELDS = [
    "date",
    "account_id",
    "spend",
    "clicks",
    "impressions",
    "all_conversions",
]

YESTERDAY = date.today() - timedelta(days=1)


def fetch_all_accounts(day):
    """One request for all clients — per-account filter mixes accounts."""
    params = {
        "api_key": WINDSOR_API_KEY,
        "date_from": str(day),
        "date_to": str(day),
        "fields": ",".join(FIELDS),
    }
    resp = requests.get(WINDSOR_BASE, params=params, timeout=(10, 30))
    resp.raise_for_status()
    return resp.json().get("data", [])


def aggregate_rows(rows):
    spend = sum(float(r.get("spend", 0) or 0) for r in rows)
    clicks = sum(int(r.get("clicks", 0) or 0) for r in rows)
    imp = sum(int(r.get("impressions", 0) or 0) for r in rows)
    donors = sum(int(r.get("all_conversions", 0) or 0) for r in rows)
    return {
        "spend": round(spend, 2),
        "donors": donors,
        "rec": 0,
        "einzel": donors,
        "imp": imp,
        "clicks": clicks,
        "lpvisits": clicks,
    }


def run():
    data_root = Path(__file__).parent.parent / "data"

    needs_update = {}
    for client_id in CLIENTS:
        path = data_root / client_id / "google.json"
        if path.exists():
            existing = json.loads(path.read_text())
        else:
            existing = {"updated": "", "rows": []}
        if str(YESTERDAY) not in {r["date"] for r in existing["rows"]}:
            needs_update[client_id] = existing

    if not needs_update:
        print("All Google clients already up to date.")
        return

    print(f"Fetching Google Ads / {YESTERDAY} (all accounts, one request)...")
    all_rows = fetch_all_accounts(YESTERDAY)

    by_account = {}
    for row in all_rows:
        acc_id = str(row.get("account_id", ""))
        by_account.setdefault(acc_id, []).append(row)

    for client_id, existing in needs_update.items():
        account_id = CLIENTS[client_id]
        acc_rows = by_account.get(str(account_id), [])
        metrics = aggregate_rows(acc_rows)
        row = {"date": str(YESTERDAY), **metrics}

        existing["rows"].append(row)
        existing["rows"].sort(key=lambda r: r["date"])
        existing["updated"] = str(date.today())

        path = data_root / client_id / "google.json"
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        s, d, c = row["spend"], row["donors"], row["clicks"]
        print(f"  {client_id}: spend={s} donors={d} clicks={c}")


if __name__ == "__main__":
    run()
