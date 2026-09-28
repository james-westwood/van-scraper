"""AA Cars (theaa.com) adapter.

Two page types, both allowed by robots.txt at time of writing:
  * browse pages  (/used-vans/<make>/<model>, /used-vans/electric ...):
    a SAMPLE of listings, parsed from link cards -> partial discovery.
  * detail pages  (/used-vans/cardetails/<id>): full facts for one van ->
    used to enrich candidates and to monitor starred vans.

Parsing is anchored on things unlikely to change with a redesign: the
/used-vans/cardetails/<id> URL shape, the og:title meta tag, and visible
labels like "Mileage:". No CSS class names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from ..classify import parse_price

BASE = "https://www.theaa.com"
DETAIL_RE = re.compile(r"/used-vans/cardetails/([\w-]+)")


def listing_id(url: str) -> str | None:
    m = DETAIL_RE.search(url)
    return f"aa:{m.group(1)}" if m else None


@dataclass
class Card:
    listing_id: str
    url: str
    title: str
    price: int | None
    plus_vat: bool | None


def parse_browse_page(html: str) -> list[Card]:
    """Every distinct listing linked from a browse page.

    A card links to the same listing several times (image, title, price
    block); we keep the richest link text per id: the one containing a price.
    """
    soup = BeautifulSoup(html, "html.parser")
    best: dict[str, tuple[str, str]] = {}
    for a in soup.find_all("a", href=DETAIL_RE):
        lid = listing_id(a["href"])
        text = " ".join(a.get_text(" ").split())
        if not lid or not text:
            continue
        prev = best.get(lid)
        has_price = "£" in text
        if prev is None or (has_price and "£" not in prev[1]) or \
                (has_price == ("£" in prev[1]) and len(text) > len(prev[1])):
            href = a["href"] if a["href"].startswith("http") else BASE + a["href"]
            best[lid] = (href.split("?")[0], text)

    cards = []
    for lid, (url, text) in best.items():
        price, plus_vat = parse_price(text)
        # Card text is "From £120 p/m £5,488 + VAT <title>" or
        # "£22,344 + VAT <title>". The title is what follows the last price.
        title = re.split(r"£[\d,]+(?:\s*\+\s*VAT)?", text)[-1].strip() or text
        if "p/m" in text:  # the first £ was a monthly figure; re-read the real price
            prices = re.findall(r"£\s?([\d,]{4,})\s*(\+\s*VAT)?", text)
            if prices:
                price = int(prices[-1][0].replace(",", ""))
                plus_vat = bool(prices[-1][1])
        cards.append(Card(lid, url, title, price, plus_vat))
    return cards


@dataclass
class Detail:
    listing_id: str
    url: str
    title: str | None
    price: int | None
    plus_vat: bool | None
    year: int | None
    mileage: int | None
    dealer: str | None
    registration: str | None
    sold: bool


def parse_detail_page(html: str, url: str) -> Detail:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.get_text(" ").split())

    og = soup.find("meta", attrs={"property": "og:title"}) or \
        soup.find("meta", attrs={"name": "og:title"})
    title = og["content"].strip() if og and og.get("content") else None
    if not title and soup.find("h1"):
        title = " ".join(soup.find("h1").get_text(" ").split())

    # The asking price sits just before the <h1>. The nav menu also contains
    # prices ("Used vans under £30,000"), so never take the first £ on the page.
    price, plus_vat = None, None
    h1 = soup.find("h1")
    h1_text = " ".join(h1.get_text(" ").split()) if h1 else None
    idx = text.find(h1_text) if h1_text else -1
    if idx > 0:
        hits = re.findall(r"£\s?([\d,]{4,})\s*(\+\s*VAT)?", text[max(0, idx - 250):idx])
        if hits:
            price, plus_vat = int(hits[-1][0].replace(",", "")), bool(hits[-1][1])
    if price is None:  # fallback: first explicit "+ VAT" price (nav has none)
        m = re.search(r"£\s?([\d,]{4,})\s*(\+\s*VAT)", text)
        if m:
            price, plus_vat = int(m.group(1).replace(",", "")), True

    year = _int_after(r"Year:\s*(\d{4})", text)
    mileage = _int_after(r"Mileage:\s*([\d,]+)", text)
    reg_m = re.search(r"Vehicle history check\s+For\s+([A-Z0-9]{5,8})\b", text)
    dealer_m = re.search(r"Contact the dealer\s+(.+?)\s+\d{5}\s?\d{3}", text)
    sold = bool(re.search(r"has now been sold|no longer available", text, re.I))

    return Detail(
        listing_id=listing_id(url) or url, url=url, title=title,
        price=price, plus_vat=plus_vat, year=year, mileage=mileage,
        dealer=dealer_m.group(1).strip() if dealer_m else None,
        registration=reg_m.group(1) if reg_m else None, sold=sold,
    )


def _int_after(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1).replace(",", "")) if m else None
