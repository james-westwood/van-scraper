"""Rank candidate vans against the requirements.

The score is only for *ordering* the report. The flags carry the meaning:
a human should read the flags, not trust the number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import config
from .classify import TitleFacts


@dataclass
class Assessment:
    score: int
    price_band: str | None     # "preferred" | "stretch" | "over_ceiling" | None
    flags: list[str]


def assess(facts: TitleFacts, price_inc_vat: int | None,
           year: int | None, mileage: int | None,
           vat_conflict: bool = False) -> Assessment:
    flags = list(facts.flags)
    score = 0

    score += {"tier1": 40, "tier2": 20, "watch": 5}.get(facts.tier or "", 0)
    score += {3: 15, 2: 12}.get(facts.roof or 0, 0)
    if facts.wheelbase and facts.wheelbase >= 3:
        score += 5

    b = facts.battery_kwh
    if b is None:
        flags.append("battery size unknown - older vans may have small packs")
    elif b < config.SMALL_BATTERY_KWH:
        flags.append(f"small battery ({b:g}kWh) - roughly 100 real miles, expect a charging stop on longer trips")
        score -= 10
    elif b >= config.BIG_BATTERY_KWH:
        score += 15
    else:
        score += 5

    band = None
    if price_inc_vat is None:
        flags.append("price not found")
    elif price_inc_vat <= config.PRICE_PREFERRED_INC_VAT:
        band, score = "preferred", score + 20
    elif price_inc_vat <= config.PRICE_CEILING_INC_VAT:
        band, score = "stretch", score + 5
        flags.append(f"stretch price (£{price_inc_vat:,} inc VAT)")
    else:
        band = "over_ceiling"
        flags.append(f"over ceiling (£{price_inc_vat:,} inc VAT)")

    if vat_conflict:
        flags.append("VAT conflict: title says NO VAT, price says +VAT - ask dealer")

    if year and mileage is not None:
        age = max(date.today().year - year, 1)
        if age >= 2 and mileage / age < config.LOW_MILES_PER_YEAR:
            flags.append(f"very low mileage for age ({mileage:,} mi in ~{age} yrs)"
                         " - check MOT history")

    return Assessment(score=score, price_band=band, flags=flags)
