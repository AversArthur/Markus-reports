"""
Facebook Ads pipeline via Windsor.ai.

Fetches yesterday's data from Windsor.ai (all accounts in one request)
and appends one row per client to data/{client_id}/facebook.json.

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
WINDSOR_ALL = "https://connectors.windsor.ai/all"

CLIENTS = {
    "vogelschutz": "903769018989508",
    "famev": "328858242",
    "fruchtalarm": "2778612375525973",
    "reporter_ohne_grenzen": "953604141392267",
    "rettungshunde": "671236841953978",
    "sound_of_peace": "25347774738215701",
}

FIELDS = [
    "date",
    "account_id",
    "spend",
    "impressions",
    "link_clicks",
    "actions_landing_page_view",
    "actions_offsite_conversion_fb_pixel_purchase",  # Purchase
    "conversions_donate_website",                    # Website Donations
]

YESTERDAY = date.today() - timedelta(days=1)


def fetch_all_accounts(day):
    """One request for all clients — per-account filter is unreliable."""
    params = {
        "api_key": WINDSOR_API_KEY,
        "date_from": str(day),
        "date_to": str(day),
        "fields": ",".join(FIELDS),
    }
    resp = requests.get(WINDSOR_ALL, params=params, timeout=(10, 30))
    resp.raise_for_status()
    return resp.json().get("data", [])


def aggregate_rows(rows):
    spend = sum(float(r.get("spend", 0) or 0) for r in rows)
    imp = sum(int(r.get("impressions", 0) or 0) for r in rows)
    clicks = sum(int(r.get("link_clicks", 0) or 0) for r in rows)
    lpvisits = sum(
        int(r.get("actions_landing_page_view", 0) or 0) for r in rows
    )
    einzel = sum(
        int(r.get(
            "actions_offsite_conversion_fb_pixel_purchase", 0
        ) or 0) for r in rows
    )
    rec = sum(
        int(r.get("conversions_donate_website", 0) or 0)
        for r in rows
    )
    return {
        "spend": round(spend, 2),
        "donors": einzel + rec,
        "rec": rec,
        "einzel": einzel,
        "imp": imp,
        "clicks": clicks,
        "lpvisits": lpvisits,
    }


def run():
    data_root = Path(__file__).parent.parent / "data"

    # Only process clients that don't yet have yesterday's row
    needs_update = {}
    for client_id in CLIENTS:
        path = data_root / client_id / "facebook.json"
        if path.exists():
            existing = json.loads(path.read_text())
        else:
            existing = {"updated": "", "rows": []}
        if str(YESTERDAY) not in {r["date"] for r in existing["rows"]}:
            needs_update[client_id] = existing

    if not needs_update:
        print("All FB clients already up to date.")
        return

    print(f"Fetching FB / {YESTERDAY} (all accounts, one request)...")
    all_rows = fetch_all_accounts(YESTERDAY)

    # Group Windsor rows by account_id
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

        path = data_root / client_id / "facebook.json"
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        s, d, c = row["spend"], row["donors"], row["clicks"]
        print(f"  {client_id}: spend={s} donors={d} clicks={c}")


if __name__ == "__main__":
    run()
