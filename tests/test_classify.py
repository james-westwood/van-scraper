"""Tests use real listing titles seen on AA Cars / dealer sites, Sept 2026."""

import pytest

from vanscraper.classify import classify_title, parse_price, price_inc_vat
from vanscraper.score import assess

# (title, expected tier, expected roof, expected battery, should_pass_stage1)
REAL_TITLES = [
    ("Peugeot Boxer 435 110kWh Professional Panel Van 5dr Electric Auto L3 H2 (22kW",
     "tier1", 2, 110.0, True),
    ("FORD TRANSIT 390 68Kwh Trend Panel Van 5Dr Electric Auto Rwd L3 H2 (269 Ps)",
     "tier2", 2, 68.0, True),
    ("Ford Transit Custom E-320 L1 Rwd 160kW 65kWh H1 Van Limited Auto",
     None, 1, 65.0, False),
    ("FORD TRANSIT CUSTOM 320 65Kwh Limited Panel Van 5Dr Electric Auto L2 H1 (136 Ps)",
     None, 1, 65.0, False),
    ("FORD TRANSIT CUSTOM E-Transit Custom 320 L2 Hi Rwd 100Kw 65Kwk Limited Panel Van",
     None, None, 65.0, False),
    ("Ford Transit Courier E-Transit Courier 100kW 43kWh Trend Van Auto",
     None, None, 43.0, False),
    ("Volkswagen Transporter T32 Lwb Electric 160kW 65kWh Commerce Pro S Kombi Van Auto",
     None, None, 65.0, False),
    ("BYD ETP3 ELECTRIC 100Kw 45Kwh Auto", None, None, 45.0, False),
    ("Peugeot Boxer 2.2 BlueHDi 335 Professional Panel Van 5dr Diesel Manual L3 H2 E",
     "tier1", 2, None, False),
    ("Peugeot Boxer BLUEHDI DROPSIDE 335 L3", "tier1", None, None, False),
]


@pytest.mark.parametrize("title,tier,roof,battery,passes", REAL_TITLES)
def test_real_titles(title, tier, roof, battery, passes):
    f = classify_title(title)
    assert f.tier == tier
    assert f.roof == roof
    assert f.battery_kwh == battery
    assert (f.rejected_reason is None) is passes, f.rejected_reason


def test_diesel_boxer_rejected_as_diesel_not_as_platform():
    f = classify_title("Peugeot Boxer 2.2 BlueHDi 335 Diesel Manual L3 H2")
    assert f.rejected_reason == "diesel"


def test_ambiguous_hi_is_flagged_not_guessed():
    f = classify_title("Citroen e-Relay L3 Hi 75kWh Electric Van")
    assert f.roof is None
    assert any("ambiguous" in fl for fl in f.flags)
    assert f.rejected_reason is None  # unknown roof is kept for a human look


def test_power_kw_is_not_mistaken_for_battery():
    assert classify_title("Vauxhall Movano Electric 90kW L3 H2").battery_kwh is None


def test_byd_large_van_goes_to_watch_list():
    f = classify_title("BYD ETP7 Electric L3 H2 Panel Van")  # hypothetical future model
    assert f.tier == "watch"


@pytest.mark.parametrize("text,amount,plus_vat", [
    ("£19,350 + VAT", 19350, True),
    ("£25,000 + VAT", 25000, True),
    ("£16,889", 16889, False),
    ("only £21,299 Plus Vat", 21299, True),
])
def test_parse_price(text, amount, plus_vat):
    assert parse_price(text) == (amount, plus_vat)


def test_vat_added_for_private_buyer():
    assert price_inc_vat(19350, True) == 23220
    assert price_inc_vat(16889, False) == 16889


def test_etransit_colchester_assessment():
    """The starred E-Transit: stretch-free price, mid battery, suspicious mileage."""
    f = classify_title("FORD TRANSIT 390 68Kwh Trend Panel Van 5Dr Electric Auto Rwd L3 H2")
    a = assess(f, price_inc_vat=23220, year=2022, mileage=4137)
    assert a.price_band == "preferred"
    assert any("MOT history" in fl for fl in a.flags)


def test_boxer_110_ranks_above_etransit():
    boxer = assess(classify_title("Peugeot Boxer 435 110kWh Electric Auto L3 H2"),
                   price_inc_vat=30000, year=2025, mileage=2500)
    transit = assess(classify_title("FORD TRANSIT 390 68Kwh Electric Auto L3 H2"),
                     price_inc_vat=23220, year=2022, mileage=4137)
    assert boxer.score > transit.score
    assert boxer.price_band == "stretch"


def test_small_battery_flagged():
    a = assess(classify_title("Peugeot e-Boxer 37kWh L2 H2 Electric"),
               price_inc_vat=18000, year=2021, mileage=30000)
    assert any("small battery" in fl for fl in a.flags)


def test_first_gen_70kwh_relay_gets_range_warning():
    """The Worcester e-Relay: cheap, right platform, but ~100 real miles."""
    a = assess(classify_title("Citroen e-Relay 35 70kWh Enterprise Auto L3 High Roof 5dr (Heavy)"),
               price_inc_vat=15599, year=2022, mileage=20100)
    assert a.price_band == "preferred"
    assert any("small battery" in fl for fl in a.flags)
