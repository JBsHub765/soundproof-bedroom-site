import os, csv, json, datetime, pathlib, urllib.request

API_KEY = os.environ.get('PLAUSIBLE_API_KEY')
SITE = os.environ.get('PLAUSIBLE_SITE_ID')

HEADERS = {'Authorization': f'Bearer {API_KEY}'}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main():
    today = datetime.date.today()
    yday = today - datetime.timedelta(days=1)
    base = 'https://plausible.io/api/v1'
    agg = get(f"{base}/stats/aggregate?site_id={SITE}&period=day&date={yday}&metrics=visitors,pageviews")
    brk = get(f"{base}/stats/breakdown?site_id={SITE}&period=day&date={yday}&property=event:page&metrics=pageviews,visitors&limit=1000")
    outdir = pathlib.Path('_reports')
    outdir.mkdir(exist_ok=True)
    path = outdir / f"plausible-{today.strftime('%Y-%m')}.csv"

    rows = []
    if path.exists():
        with path.open() as fh:
            rows = list(csv.reader(fh))
    header = ['date','page','pageviews','visitors','total_pageviews','total_visitors']
    if not rows or rows[0] != header:
        rows = [header]
    total_pv = agg.get('results', {}).get('pageviews', 0) if agg.get('results') else 0
    total_v = agg.get('results', {}).get('visitors', 0) if agg.get('results') else 0
    for item in brk.get('results', []):
        rows.append([
            yday.isoformat(),
            item['page'],
            str(item.get('pageviews', 0)),
            str(item.get('visitors', 0)),
            str(total_pv),
            str(total_v)
        ])
    with path.open('w', newline='') as fh:
        csv.writer(fh).writerows(rows)
    print('Wrote', path)

if __name__ == '__main__':
    main()
