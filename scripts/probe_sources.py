"""Which candidate discovery sources may we use, and what do their pages look like?

Run on GitHub Actions (the Claude sandbox can't reach these hosts):
    uv run python -m scripts.probe_sources
(run as a module so the repo root, and so vanscraper, is importable)
For each URL: robots.txt verdict, HTTP status, and how many listing-like links
the page contains. Use the output to decide which adapters to write next.
Nothing disallowed is ever requested.
"""
import re
import sys

from vanscraper.fetch import PoliteClient, RobotsDisallowed

CANDIDATES = [
    ("AA full search (expected: disallowed)",
     "https://www.theaa.com/used-cars/displaycars?fueltype=electric&classid=111&page=1"),
    ("AA electric vans browse", "https://www.theaa.com/used-vans/electric"),
    ("Cazoo all vans", "https://www.cazoo.co.uk/vans/"),
    ("Cazoo electric vans (guessed path)", "https://www.cazoo.co.uk/vans/electric/"),
    ("Cazoo Peugeot vans", "https://www.cazoo.co.uk/vans/peugeot/"),
    ("Motors vans", "https://www.motors.co.uk/vans/"),
    ("Van Monster Boxer", "https://www.vanmonster.com/en-gb/find-a-used-van/used-van-search/peugeot/boxer"),
    ("AutoTrader vans (expected: disallowed)",
     "https://www.autotrader.co.uk/van-search?fuel-type=Electric"),
]
LISTING_LINK = re.compile(r'href="[^"]*(cardetails|cars-for-sale|vans-for-sale|van-details|/used-van/)[^"]*"')


def main() -> int:
    pc = PoliteClient()
    for name, url in CANDIDATES:
        try:
            r = pc.get(url)
            links = len(set(LISTING_LINK.findall(r.text))) if r.status_code == 200 else 0
            kinds = sorted(set(m.group(1) for m in LISTING_LINK.finditer(r.text)))
            print(f"ALLOWED  {r.status_code}  listing-links={len(LISTING_LINK.findall(r.text)):>4} "
                  f"{kinds}  {name}")
        except RobotsDisallowed as e:
            print(f"{e.reason.upper():<8}  --                                {name}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR    {type(e).__name__}: {e}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
