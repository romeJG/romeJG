#!/usr/bin/env python3
"""
Scrape real ALL-TIME daily contribution counts from GitHub's public,
unauthenticated contributions endpoint (the same fragment the profile page
itself uses), one calendar year at a time via its from/to query params, and
write data/contributions.json with the raw days plus derived stats
(current streak, longest streak, best day, monthly totals) across the user's
whole account history.

No token, no auth, no GraphQL -- just the public HTML GitHub already serves.
Run daily by .github/workflows/update-profile-art.yml.
"""
import datetime
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "YOUR_GITHUB_USERNAME")
API_URL = f"https://api.github.com/users/{USERNAME}"
CONTRIB_URL = f"https://github.com/users/{USERNAME}/contributions"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")
HEADERS = {"User-Agent": "profile-readme-bot/1.0"}


def join_year():
    """First year of account history; falls back to a 5-year window if the
    unauthenticated API call is rate-limited."""
    try:
        resp = requests.get(API_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return int(resp.json()["created_at"][:4])
    except Exception as e:
        print(f"couldn't fetch join year ({e}); defaulting to a 5-year window", file=sys.stderr)
        return datetime.date.today().year - 5


def fetch_year(year):
    """Days within a single calendar year (extra days GitHub pads onto the
    surrounding weeks are filtered out so years don't overlap when merged)."""
    url = f"{CONTRIB_URL}?from={year}-01-01&to={year}-12-31"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print(f"no calendar cells found for {year} -- github markup may have changed", file=sys.stderr)
        return []

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date or not date.startswith(f"{year}-"):
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0
        days.append({"date": date, "count": count})
    return days


def fetch_all_days():
    today = datetime.date.today().isoformat()
    start_year = join_year()
    end_year = datetime.date.today().year
    merged = {}
    for year in range(start_year, end_year + 1):
        for d in fetch_year(year):
            if d["date"] > today:
                continue  # GitHub pads the current year's calendar out to Dec 31
            merged[d["date"]] = d["count"]
    if not merged:
        print("no contribution data collected across any year", file=sys.stderr)
        sys.exit(1)
    return [{"date": k, "count": v} for k, v in sorted(merged.items())]


def compute_current_streak(days):
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break the streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"])
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


if __name__ == "__main__":
    days = fetch_all_days()
    data = build_data(days)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions across "
          f"{data['range']['start']} -> {data['range']['end']}, "
          f"current streak {data['current_streak']['length']}, "
          f"longest streak {data['longest_streak']['length']}")
