"""Weekly run: discover candidate vans, enrich them, re-check starred vans.

Same contract as job-board-scraper: stateless, one JSON per run in
output/latest.json (+ dated copy). Dedup/"is this new?" lives on the
consuming Cowork side, keyed on listing_id. A source that breaks is
recorded in run_metadata.sources, never takes the run down.
"""

from __future__ import annotations

import argparse
import json
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

from . import config
from .classify import classify_title, price_inc_vat
from .fetch import PoliteClient, RobotsDisallowed
from .score import assess
from .sources import aa

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
STARRED = ROOT / "starred.json"
MAX_DETAIL_FETCHES = 40


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def van_record(detail: aa.Detail, source: str, starred: bool = False) -> dict:
    facts = classify_title(detail.classify_text())
    inc = price_inc_vat(detail.price, detail.plus_vat)
    vat_conflict = bool(detail.title and "no vat" in detail.title.lower() and detail.plus_vat)
    a = assess(facts, inc, detail.year, detail.mileage, vat_conflict)
    return {
        "listing_id": detail.listing_id,
        "source": source,
        "url": detail.url,
        "title": detail.title,
        "starred": starred,
        "sold": detail.sold,
        "platform": facts.platform,
        "tier": facts.tier,
        "fuel": facts.fuel,
        "roof": facts.roof,
        "wheelbase": facts.wheelbase,
        "battery_kwh": facts.battery_kwh,
        "year": detail.year,
        "mileage": detail.mileage,
        "price_listed": detail.price,
        "price_plus_vat": detail.plus_vat,
        "price_inc_vat": inc,
        "price_band": a.price_band,
        "dealer": detail.dealer,
        "registration": detail.registration,
        "rejected_reason": facts.rejected_reason,
        "score": a.score,
        "flags": a.flags,
        "scraped_at_utc": now(),
    }


def run(skip_discovery: bool = False) -> dict:
    started = now()
    client = PoliteClient()
    sources: list[dict] = []
    candidates: dict[str, aa.Card] = {}
    cards_seen = 0

    # 1. Discovery: AA browse pages (partial coverage by design).
    if not skip_discovery:
        for url in config.AA_BROWSE_PAGES:
            entry = {"source": "aa_browse", "url": url}
            try:
                r = client.get(url)
                r.raise_for_status()
                cards = aa.parse_browse_page(r.text)
                cards_seen += len(cards)
                kept = 0
                for c in cards:
                    f = classify_title(c.title)
                    if f.rejected_reason is None:
                        candidates.setdefault(c.listing_id, c)
                        kept += 1
                entry.update(status="ok", cards=len(cards), stage1_passed=kept)
            except RobotsDisallowed as e:
                entry.update(status=e.reason)
            except Exception as e:  # noqa: BLE001 - record, never crash the run
                entry.update(status="failed", error=f"{type(e).__name__}: {e}")
            sources.append(entry)

    # 2. Enrich Stage-1 survivors from their detail pages.
    vans: list[dict] = []
    for card in list(candidates.values())[:MAX_DETAIL_FETCHES]:
        try:
            r = client.get(card.url)
            r.raise_for_status()
            vans.append(van_record(aa.parse_detail_page(r.text, card.url), "aa"))
        except Exception as e:  # noqa: BLE001
            vans.append({"listing_id": card.listing_id, "url": card.url,
                         "title": card.title, "error": f"{type(e).__name__}: {e}"})

    # 3. Starred vans: always re-checked, whatever the filters say.
    starred_out = []
    for s in json.loads(STARRED.read_text()) if STARRED.exists() else []:
        try:
            r = client.get(s["url"])
            if r.status_code == 404:
                starred_out.append({**s, "status": "gone (404) - probably sold"})
                continue
            r.raise_for_status()
            rec = van_record(aa.parse_detail_page(r.text, s["url"]), "aa", starred=True)
            rec["note"] = s.get("note")
            rec["status"] = "sold" if rec["sold"] else "live"
            starred_out.append(rec)
        except RobotsDisallowed as e:
            starred_out.append({**s, "status": e.reason})
        except Exception as e:  # noqa: BLE001
            starred_out.append({**s, "status": f"check failed: {type(e).__name__}: {e}"})

    # The detail page can reveal what the title hid (e.g. "Fuel type: Diesel").
    detail_rejected = [v for v in vans if v.get("rejected_reason")]
    vans = [v for v in vans if not v.get("rejected_reason")]
    vans.sort(key=lambda v: v.get("score", -999), reverse=True)
    return {
        "run_metadata": {
            "run_started_utc": started,
            "run_finished_utc": now(),
            "scraper_version": config.SCRAPER_VERSION,
            "budget_inc_vat": {"preferred": config.PRICE_PREFERRED_INC_VAT,
                               "ceiling": config.PRICE_CEILING_INC_VAT},
            "coverage_note": ("AA browse pages show a sample only; the full AA "
                              "search is disallowed by robots.txt. Not exhaustive."),
            "cards_seen": cards_seen,
            "stage1_candidates": len(candidates),
            "detail_rejected": [{"listing_id": v["listing_id"], "reason": v["rejected_reason"]}
                                for v in detail_rejected],
            "sources": sources,
        },
        "starred": starred_out,
        "vans": vans,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--starred-only", action="store_true",
                    help="skip discovery, just re-check starred vans")
    args = ap.parse_args()
    try:
        report = run(skip_discovery=args.starred_only)
    except Exception:  # last-ditch: still write something the consumer can read
        report = {"run_metadata": {"run_started_utc": now(), "fatal": traceback.format_exc()},
                  "starred": [], "vans": []}
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "runs").mkdir(exist_ok=True)
    body = json.dumps(report, indent=2, ensure_ascii=False)
    (OUTPUT / "latest.json").write_text(body)
    (OUTPUT / "runs" / f"{date.today().isoformat()}.json").write_text(body)
    m = report["run_metadata"]
    print(f"cards seen: {m.get('cards_seen')}, candidates: {m.get('stage1_candidates')}, "
          f"vans reported: {len(report['vans'])}, starred checked: {len(report['starred'])}")


if __name__ == "__main__":
    main()
