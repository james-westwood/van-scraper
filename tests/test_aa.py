from pathlib import Path

from vanscraper.classify import classify_title
from vanscraper.sources import aa

FIX = Path(__file__).parent / "fixtures"


def test_browse_page_cards():
    cards = {c.listing_id: c for c in aa.parse_browse_page((FIX / "aa_browse_sample.html").read_text())}
    assert set(cards) == {"aa:108-249837", "aa:99-111111", "aa:154-79799"}
    boxer = cards["aa:99-111111"]
    assert boxer.price == 25000 and boxer.plus_vat is True
    assert "110kWh" in boxer.title and "£" not in boxer.title
    # finance card: monthly figure must not be taken as the price
    assert cards["aa:154-79799"].price == 5488


def test_only_electric_high_roof_survives_stage1():
    cards = aa.parse_browse_page((FIX / "aa_browse_sample.html").read_text())
    passed = [c.listing_id for c in cards if classify_title(c.title).rejected_reason is None]
    assert passed == ["aa:99-111111"]


def test_detail_page_ignores_nav_prices():
    url = "https://www.theaa.com/used-vans/cardetails/168-152844"
    d = aa.parse_detail_page((FIX / "aa_detail_etransit.html").read_text(), url)
    assert d.listing_id == "aa:168-152844"
    assert d.price == 19350 and d.plus_vat is True      # not £30,000 from the nav
    assert d.year == 2022 and d.mileage == 4137
    assert d.registration == "VO72UCB"
    assert d.dealer == "Lookers Ford Transit Centre Colchester"
    assert d.sold is False
