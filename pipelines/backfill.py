"""
Backfill script.

Fetches the last N days from Windsor.ai for all configured clients and
OVERWRITES the existing JSON files with real data.

Usage:
  python pipelines/backfill.py                    # last 90 days (default)
  python pipelines/backfill.py --days 30
  python pipelines/backfill.py --connector google_ads
  python pipelines/backfill.py --connector facebook
"""

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

WINDSOR_API_KEY = os.environ["WINDSOR_API_KEY"]
WINDSOR_ALL = "https://connectors.windsor.ai/all"
WINDSOR_GADS = "https://connectors.windsor.ai/google_ads"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GOOGLE_CLIENTS = {
    "vogelschutz": ["537-317-1947"],
    # "famev": ["XXX-XXX-XXXX"],
}

FACEBOOK_CLIENTS = {
    "vogelschutz": "903769018989508",
    "famev": "328858242",
    "fruchtalarm": "2778612375525973",
    "reporter_ohne_grenzen": "953604141392267",
    "rettungshunde": "671236841953978",
    "sound_of_peace": "25347774738215701",
}

# Windsor /all endpoint with flat action fields (no nested arrays)
FACEBOOK_FIELDS = [
    "date",
    "account_id",
    "spend",
    "impressions",
    "link_clicks",
    "actions_landing_page_view",
    "actions_offsite_conversion_fb_pixel_purchase",  # Einzelspende / Purchase
    "conversions_donate_website",                    # Website Donations / Dauerspende
]

GOOGLE_FIELDS = ["date", "spend", "clicks", "impressions", "all_conversions"]


def fetch_fb_all_accounts(date_from, date_to):
    """Fetch all FB accounts at once — Windsor's per-account filter is unreliable."""
    params = {
        "api_key": WINDSOR_API_KEY,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "fields": ",".join(FACEBOOK_FIELDS + ["account_id"]),
    }
    resp = requests.get(WINDSOR_ALL, params=params, timeout=(10, 60))
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_google_range(account_id, date_from, date_to):
    params = {
        "api_key": WINDSOR_API_KEY,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "fields": ",".join(GOOGLE_FIELDS),
        "account_id": account_id,
    }
    resp = requests.get(WINDSOR_GADS, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json().get("data", [])


def fb_rows_to_daily(raw_rows):
    by_date = {}
    for r in raw_rows:
        d = str(r.get("date", ""))[:10]
        if not d:
            continue
        if d not in by_date:
            by_date[d] = {
                "spend": 0.0, "donors": 0, "rec": 0, "einzel": 0,
                "imp": 0, "clicks": 0, "lpvisits": 0,
            }
        e = by_date[d]
        e["spend"] += float(r.get("spend", 0) or 0)
        e["imp"] += int(r.get("impressions", 0) or 0)
        e["clicks"] += int(r.get("link_clicks", 0) or 0)
        e["lpvisits"] += int(
            r.get("actions_landing_page_view", 0) or 0
        )
        einzel = int(
            r.get("actions_offsite_conversion_fb_pixel_purchase", 0) or 0
        )
        rec = int(r.get("conversions_donate_website", 0) or 0)
        e["einzel"] += einzel
        e["rec"] += rec
        e["donors"] += einzel + rec
    return by_date


def google_rows_to_daily(raw_rows):
    by_date = {}
    for r in raw_rows:
        d = str(r.get("date", ""))[:10]
        if not d:
            continue
        if d not in by_date:
            by_date[d] = {
                "spend": 0.0, "donors": 0, "rec": 0, "einzel": 0,
                "imp": 0, "clicks": 0, "lpvisits": 0,
            }
        e = by_date[d]
        e["spend"] += float(r.get("spend", 0) or 0)
        e["imp"] += int(r.get("impressions", 0) or 0)
        e["clicks"] += int(r.get("clicks", 0) or 0)
        e["lpvisits"] += int(r.get("clicks", 0) or 0)
        donors = int(r.get("all_conversions", 0) or 0)
        e["donors"] += donors
        e["einzel"] += donors
    return by_date


def build_rows(by_date, date_from, date_to):
    rows = []
    cur = date_from
    while cur <= date_to:
        d = str(cur)
        e = by_date.get(d, {})
        rows.append({
            "date": d,
            "spend": round(e.get("spend", 0.0), 2),
            "donors": e.get("donors", 0),
            "rec": e.get("rec", 0),
            "einzel": e.get("einzel", 0),
            "imp": e.get("imp", 0),
            "clicks": e.get("clicks", 0),
            "lpvisits": e.get("lpvisits", 0),
        })
        cur += timedelta(days=1)
    return rows


def save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"updated": str(date.today()), "rows": rows},
        indent=2, ensure_ascii=False,
    ))
    total = sum(r["spend"] for r in rows)
    donors = sum(r["donors"] for r in rows)
    non_zero = sum(1 for r in rows if r["spend"] > 0)
    print(f"  OK {len(rows)} days ({non_zero} with data)"
          f" — spend: {total:.2f} EUR, donors: {donors}")


def backfill_facebook(data_root, days):
    date_to = date.today() - timedelta(days=1)
    date_from = date_to - timedelta(days=days - 1)

    print("\n[FB] Fetching all accounts in one request...")
    all_raw = fetch_fb_all_accounts(date_from, date_to)
    print(f"  {len(all_raw)} total rows received")

    # Split rows by account_id
    by_account = {}
    for row in all_raw:
        acc_id = str(row.get("account_id", ""))
        if acc_id not in by_account:
            by_account[acc_id] = []
        by_account[acc_id].append(row)

    for client_id, account_id in FACEBOOK_CLIENTS.items():
        acc_rows = by_account.get(str(account_id), [])
        print(f"\n[FB] {client_id} ({account_id}) — {len(acc_rows)} rows")
        if not acc_rows:
            print("  no data — skipping")
            continue
        by_date = fb_rows_to_daily(acc_rows)
        rows = build_rows(by_date, date_from, date_to)
        save(data_root / client_id / "facebook.json", rows)


def backfill_google(data_root, days):
    date_to = date.today() - timedelta(days=1)
    date_from = date_to - timedelta(days=days - 1)

    for client_id, account_ids in GOOGLE_CLIENTS.items():
        if isinstance(account_ids, str):
            account_ids = [account_ids]
        print(f"\n[Google] {client_id}")
        all_raw = []
        for aid in account_ids:
            print(f"  account {aid}...")
            raw = fetch_google_range(aid, date_from, date_to)
            all_raw.extend(raw)
            print(f"    {len(raw)} rows")
        by_date = google_rows_to_daily(all_raw)
        rows = build_rows(by_date, date_from, date_to)
        save(data_root / client_id / "google.json", rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument(
        "--connector",
        choices=["google_ads", "facebook", "all"],
        default="all",
    )
    args = parser.parse_args()
    data_root = Path(__file__).parent.parent / "data"

    if args.connector in ("google_ads", "all"):
        backfill_google(data_root, args.days)

    if args.connector in ("facebook", "all"):
        backfill_facebook(data_root, args.days)

    print("\nDone.")


if __name__ == "__main__":
    main()
