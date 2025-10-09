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
from typing import Any, Dict, Optional

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
        property: The property to break down by (e.g. 'page', 'event_name').
        metrics: Comma-separated metrics (e.g. 'pageviews', 'visitors', 'events').
        period: The period to query ('day', 'week', 'month', etc.).
        date: Specific date in ISO format (YYYY-MM-DD) to get metrics for.

    Returns:
        Parsed JSON response containing the results list.
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
    return _request(API_ENDPOINT, params, headers)


def main() -> None:
    api_key = os.environ.get("PLAUSIBLE_API_KEY")
    site_id = os.environ.get("PLAUSIBLE_SITE_ID")
    if not api_key or not site_id:
        print(
            "Missing PLAUSIBLE_API_KEY or PLAUSIBLE_SITE_ID environment variables",
            file=sys.stderr,
        )
        sys.exit(1)

    # Use yesterday's date to allow Plausible time to aggregate data
    today = _dt.date.today()
    yesterday = today - _dt.timedelta(days=1)
    date_str = yesterday.isoformat()

    # Fetch pageviews breakdown by page. If the request fails (e.g. due to
    # network issues or an unexpected API response), fall back to an empty result
    try:
        page_data = fetch_breakdown(
            site_id=site_id,
            api_key=api_key,
            property="page",
            metrics="pageviews",
            period="day",
            date=date_str,
        )
    except Exception as exc:
        print(f"Failed to fetch pageviews: {exc}", file=sys.stderr)
        page_data = {"results": []}

    # Fetch events breakdown by page. Plausible's Stats API v1 can return
    # HTTP errors when combining certain properties/metrics; wrap in a
    # try/except so a failure doesn't cause the workflow to fail.
    try:
        event_data = fetch_breakdown(
            site_id=site_id,
            api_key=api_key,
            property="event:page",
            metrics="events",
            period="day",
            date=date_str,
        )
    except Exception as exc:
        print(f"Failed to fetch events: {exc}", file=sys.stderr)
        event_data = {"results": []}

    # Prepare report directory and filename
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    reports_dir = repo_root / "_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    outfile = reports_dir / f"plausible-{yesterday.strftime('%Y-%m')}.csv"

    # Read existing rows if file exists
    rows: list[list[str]] = []
    if outfile.exists():
        with outfile.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
    if not rows or rows[0] != ["date", "type", "name", "value"]:
        rows = [["date", "type", "name", "value"]]

    # Append new rows for pageviews
    for result in page_data.get("results", []):
        name = result.get("page", "")
        value = result.get("pageviews", 0)
        rows.append([date_str, "pageviews", name, str(value)])

    # Append new rows for events. When breaking down by event:page,
    # Plausible returns a ``page`` key for each result. ``events`` counts both
    # pageviews and custom events (e.g., our affiliate clicks) on that page.
    for result in event_data.get("results", []):
        name = result.get("page", "")
        value = result.get("events", 0)
        rows.append([date_str, "events", name, str(value)])

    # Write CSV file
    with outfile.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    print(f"Wrote {outfile}")


if __name__ == "__main__":
    main()