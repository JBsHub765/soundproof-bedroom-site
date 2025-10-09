"""
Fetch analytics data from Plausible and save it to a CSV report.

This script is intended to be run by GitHub Actions. It uses the PLAUSIBLE_API_KEY
and PLAUSIBLE_SITE_ID environment variables to authenticate with Plausible's REST
API. The script collects pageview metrics and event counts for a single day
(yesterday) and writes them to a CSV file under the `_reports` directory.

The CSV file will have the following columns:
    date: ISO date (YYYY-MM-DD)
    type: 'pageviews' or 'events'
    name: page path for pageviews, or event name for events
    value: count of the metric

To customise the metrics or time period, modify the parameters passed to
`fetch_breakdown` below. See Plausible API docs for details:
https://plausible.io/docs/stats-api#stats-breakdown
"""

import csv
import datetime as _dt
import json
import os
import pathlib
import sys
from typing import Any, Dict

import urllib.request
import urllib.parse


API_ENDPOINT = "https://plausible.io/api/v1/stats/breakdown"


def _request(endpoint: str, params: Dict[str, str], headers: Dict[str, str]) -> Dict[str, Any]:
    """Send a GET request and return the parsed JSON response."""
    query = urllib.parse.urlencode(params)
    url = f"{endpoint}?{query}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        data = resp.read().decode(charset)
    return json.loads(data)


def fetch_breakdown(site_id: str, api_key: str, property: str, metrics: str, period: str, date: str) -> Dict[str, Any]:
    """Fetch a breakdown of metrics from Plausible API.

    Args:
        site_id: The Plausible site ID (domain) to query.
        api_key: The API key for authentication.
        property: The property to break down by (e.g. 'page', 'event:page').
        metrics: Comma-separated metrics (e.g. 'pageviews', 'events').
        period: The period to query ('day', 'week', etc.).
        date: Specific date in ISO format (YYYY-MM-DD).

    Returns:
        Parsed JSON response.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    params = {
        "site_id": site_id,
        "property": property,
        "metrics": metrics,
        "period": period,
        "date": date,
        }
           try:
            return _request(API_ENDPOINT, params, headers)
        except Exception as exc:
        print(f"Failed to fetch breakdown: {exc}", file=sys.stderr)
        return {"results": []}


def main() -> None:
        api_key = os.environ.get("PLAUSIBLE_API_KEY")
    sit    e_id = os.environ.get("PLAUSIBLE_SITE_ID")
        if not api_key or not site_id:
        print("Missing PLAUSIBLE_API_KEY or PLAUSIBLE_SITE_ID", file=sys.stderr)
        sys.exit(1)

    # Use yesterday's date
    today = _dt.date.today()
    yesterday = today - _dt.timedelta(days=1)
    date_str = yesterday.isoformat()

    # Get pageviews by page
    page_data = fetch_breakdown(
        site_id=site_id,
        api_key=api_key,
        property="page",
        metrics="pageviews",
        period="day",
        date=date_str,
    )

    # Get events by page (counts pageviews + custom events)
    event_data = fetch_breakdown(
        site_id=site_id,
        api_key=api_key,
        property="event:page",
        metrics="events",
        period="day",
        date=date_str,
    )

    # Determine repo root and report path
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    reports_dir = repo_root / "_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    outfile = reports_dir / f"plausible-{yesterday.strftime('%Y-%m')}.csv"

    # Load existing rows
    rows = []
    if outfile.exists():
        with outfile.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)

    if not rows or rows[0] != ["date", "type", "name", "value"]:
        rows = [["date", "type", "name", "value"]]

    # Append pageviews rows
    for result in page_data.get("results", []):
        page = result.get("page", "")
        count = result.get("pageviews", 0)
        rows.append([date_str, "pageviews", page, str(count)])

    # Append events rows
    for result in event_data.get("results", []):
        page = result.get("page", "")
        count = result.get("events", 0)
        rows.append([date_str, "events", page, str(count)])

    # Write out file
    with outfile.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    print(f"Wrote {outfile}")


if __name__ == "__main__":
    main()
