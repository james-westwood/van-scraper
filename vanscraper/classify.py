"""Turn a free-text listing title into structured, filterable facts.

Everything here is pure (no I/O) so it can be unit-tested against real
listing titles. Titles are the most reliable field we get: dealers put the
model, roof code (H1/H2/H3), wheelbase (L1-L4) and battery (kWh) in them far
more consistently than they fill in structured fields.

Design rule: never silently guess. Anything we cannot read is returned as
None and surfaced as a flag, so a human sees "roof unknown" rather than the
scraper quietly treating it as a match or a miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Platforms --------------------------------------------------------------
# Tier 1: Stellantis large-van platform (Ducato-based). Widest interior of the
#         mainstream large vans -> best chance of a crosswise bed at ~6ft.
# Tier 2: other large vans with a high-roof option. Standing height yes,
#         crosswise bed probably not without flares.
# Watch:  makes with no suitable large van yet, but one is expected. Flagged
#         for a human look rather than matched or rejected.
TIER1 = [
    ("stellantis:boxer", r"\be?-?boxer\b"),
    ("stellantis:ducato", r"\be?-?ducato\b"),
    ("stellantis:relay", r"\b[eë]?-?relay\b"),
    ("stellantis:movano", r"\bmovano\b"),
    ("stellantis:jumper", r"\be?-?jumper\b"),
]
TIER2 = [
    ("ford:transit", r"\be?-?transit\b"),
    ("mercedes:sprinter", r"\be?-?sprinter\b"),
    ("renault:master", r"\bmaster\b"),
    ("maxus:edeliver9", r"\be?-?deliver\s?9\b"),
    ("iveco:daily", r"\be?-?daily\b"),
    ("vw:crafter", r"\be?-?crafter\b"),
]
WATCH = [("byd:large", r"\bbyd\b")]

# Smaller vans that share a name fragment with a large one (Transit Custom,
# Transit Courier...) or are simply too small. Checked before the tiers.
TOO_SMALL = [
    r"transit\s+custom", r"transit\s+courier", r"transit\s+connect",
    r"\bcustom\b", r"\bcourier\b", r"\bconnect\b",
    r"\bvivaro\b", r"\bexpert\b", r"\bdispatch\b", r"\bjumpy\b", r"\bscudo\b",
    r"\bpartner\b", r"\bberlingo\b", r"\bcombo\b", r"\bdoblo\b", r"\brifter\b",
    r"\bkangoo\b", r"\btownstar\b", r"\bcaddy\b", r"\btransporter\b",
    r"\bproace\b", r"\bvito\b", r"\betp\s?3\b", r"\bpv5\b", r"\bid\.?\s?buzz\b",
    r"\btrafic\b", r"\bprimastar\b", r"\bnv200\b", r"\bedeliver\s?[37]\b",
]

# Bodies you cannot live in even on a large platform.
WRONG_BODY = [r"\bdropside\b", r"\btipper\b", r"\bchassis\s+cab\b", r"\bluton\b",
              r"\bpick\s?-?up\b", r"\bcrew\s+cab\b", r"\bminibus\b"]

DIESEL = [r"\bdiesel\b", r"\bbluehdi\b", r"\bhdi\b", r"\btdci\b", r"\bcdi\b",
          r"\bdci\b", r"\becoblue\b", r"\bmultijet\b", r"\btdi\b", r"\bd\d{3}\b"]
PETROL = [r"\bpetrol\b", r"\becoboost\b", r"\btsi\b"]
ELECTRIC = [r"\belectric\b", r"\bkwh\b", r"\d\s?kw[hk]\b", r"\bev\b",
            r"\be-(?:transit|boxer|ducato|relay|jumper|sprinter|crafter|daily)\b",
            r"\bë-relay\b", r"\be-tech\b", r"\bedeliver\b", r"\besprinter\b"]


@dataclass
class TitleFacts:
    title: str
    platform: str | None = None      # e.g. "stellantis:boxer"
    tier: str | None = None          # "tier1" | "tier2" | "watch" | None
    fuel: str | None = None          # "electric" | "diesel" | "petrol" | None
    roof: int | None = None          # 1, 2, 3 or None if unstated
    wheelbase: int | None = None     # 1-4 or None
    battery_kwh: float | None = None
    rejected_reason: str | None = None
    flags: list[str] = field(default_factory=list)


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def parse_roof(t: str) -> tuple[int | None, bool]:
    """Return (roof_height, ambiguous). Handles 'L3 H2', 'L3H2', 'high roof'."""
    m = re.search(r"\bl\d\s?h([1-3])\b", t) or re.search(r"\bh([1-3])\b", t)
    if m:
        return int(m.group(1)), False
    if re.search(r"\bhigh[\s-]?roof\b", t):
        return 2, False
    if re.search(r"\blow[\s-]?roof\b", t):
        return 1, False
    # "L2 Hi" seen in the wild -- could be high roof, could be trim. Flag it.
    if re.search(r"\bhi\b", t):
        return None, True
    return None, False


def parse_wheelbase(t: str) -> int | None:
    m = re.search(r"\bl([1-4])\s?h?\d?\b", t)
    if m:
        return int(m.group(1))
    for name, val in (("xlwb", 4), ("lwb", 3), ("mwb", 2), ("swb", 1)):
        if re.search(rf"\b{name}\b", t):
            return val
    return None


def parse_battery(t: str) -> float | None:
    # "65kWh", "68 Kwh", and the real typo "65Kwk". Power figures are "100kW"
    # (no trailing h/k), so they don't match.
    m = re.search(r"(\d{2,3}(?:\.\d)?)\s?kw[hk]\b", t)
    return float(m.group(1)) if m else None


def classify_title(title: str) -> TitleFacts:
    t = title.lower()
    f = TitleFacts(title=title)

    if _any(DIESEL, t):
        f.fuel = "diesel"
    elif _any(ELECTRIC, t):
        f.fuel = "electric"
    elif _any(PETROL, t):
        f.fuel = "petrol"

    f.roof, roof_ambiguous = parse_roof(t)
    f.wheelbase = parse_wheelbase(t)
    f.battery_kwh = parse_battery(t)

    if _any(TOO_SMALL, t):
        f.rejected_reason = "too small (medium/small van)"
        return f
    for plat, pat in TIER1:
        if re.search(pat, t):
            f.platform, f.tier = plat, "tier1"
            break
    else:
        for plat, pat in TIER2:
            if re.search(pat, t):
                f.platform, f.tier = plat, "tier2"
                break
        else:
            for plat, pat in WATCH:
                if re.search(pat, t):
                    f.platform, f.tier = plat, "watch"
                    f.flags.append("watch-list make: check size by hand")
                    break

    if f.tier is None:
        f.rejected_reason = "not a target platform"
    elif f.fuel in ("diesel", "petrol"):
        f.rejected_reason = f"{f.fuel}"
    elif _any(WRONG_BODY, t):
        f.rejected_reason = "wrong body (dropside/luton/chassis cab etc.)"
    elif f.roof == 1:
        f.rejected_reason = "low roof (H1): no standing height"

    if f.fuel is None:
        f.flags.append("fuel not stated in title")
    if f.roof is None:
        f.flags.append("roof ambiguous ('Hi') - check" if roof_ambiguous
                       else "roof not stated - check")
    return f


# --- Price ------------------------------------------------------------------
VAT_RATE = 0.20


def parse_price(text: str) -> tuple[int | None, bool | None]:
    """'£19,350 + VAT' -> (19350, True). '£16,889' -> (16889, False).
    Returns (amount, plus_vat). plus_vat None if no price found."""
    m = re.search(r"£\s?([\d,]{3,})(?:\.\d{2})?\s*(\+\s*VAT|plus\s+vat)?", text, re.I)
    if not m:
        return None, None
    return int(m.group(1).replace(",", "")), bool(m.group(2))


def price_inc_vat(amount: int | None, plus_vat: bool | None) -> int | None:
    if amount is None:
        return None
    return round(amount * (1 + VAT_RATE)) if plus_vat else amount
