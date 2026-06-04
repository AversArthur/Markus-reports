"""
Combine pipeline.

Merges facebook.json and google.json row-by-row (by date) into combined.json.
Run after both platform pipelines:
  python pipelines/combine.py
"""

import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
KEYS = ["spend", "donors", "rec", "einzel", "imp", "clicks", "lpvisits"]


def run():
    projects = json.loads((DATA_DIR / "projects.json").read_text())

    for project in projects:
        client_id = project["id"]
        fb_path = DATA_DIR / client_id / "facebook.json"
        goog_path = DATA_DIR / client_id / "google.json"

        if not fb_path.exists() or not goog_path.exists():
            print(f"Skipping {client_id}: missing data files")
            continue

        fb = json.loads(fb_path.read_text())
        goog = json.loads(goog_path.read_text())

        by_date = defaultdict(lambda: {k: 0 for k in KEYS})
        for row in fb["rows"] + goog["rows"]:
            d = row["date"]
            for k in KEYS:
                by_date[d][k] += row.get(k, 0)

        combined_rows = [
            {"date": d, **metrics}
            for d, metrics in sorted(by_date.items())
        ]

        out_path = DATA_DIR / client_id / "combined.json"
        out_path.write_text(json.dumps(
            {"updated": fb.get("updated", ""), "rows": combined_rows},
            indent=2,
            ensure_ascii=False,
        ))
        print(f"  → {client_id}/combined.json ({len(combined_rows)} rows)")


if __name__ == "__main__":
    run()
