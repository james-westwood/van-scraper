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


# Real pages downloaded 2026-09-28 (the fixtures above are reconstructed).
def _real(lid: str) -> aa.Detail:
    html = (FIX / f"aa_detail_real_{lid}.html").read_text()
    return aa.parse_detail_page(html, f"https://www.theaa.com/used-vans/cardetails/{lid}")


def test_real_page_overview_fuel_rejects_diesel_hidden_in_title():
    d = _real("154-100207")  # "Vauxhall MOVANO 2.2 Movano L3H2 F3500 Edition T D S/S"
    assert classify_title(d.title).fuel is None
    assert d.fuel_type == "diesel"
    assert classify_title(d.classify_text()).rejected_reason == "diesel"
    assert d.dealer == "Car Motion"
    assert d.price == 8271 and d.plus_vat is True
    assert d.year == 2022 and d.mileage == 133108


def test_real_page_dealer_with_four_digit_area_code():
    d = _real("120-82607")  # Maxus eDeliver 9, dealer phone 0118 344 2202
    assert d.dealer == "Anchor Group"
    assert d.fuel_type == "electric" and d.year == 2024 and d.mileage == 20563
    f = classify_title(d.classify_text())
    assert f.rejected_reason is None and f.roof == 3 and f.battery_kwh == 88.5


def test_real_page_body_type_supplies_roof():
    d = _real("50-91967")  # e-Transit, title has no roof code
    assert d.dealer == "Sandicliffe Ford Transit Centre Nottingham"
    assert d.body_type == "high volume/high roof van"
    f = classify_title(d.classify_text())
    assert f.fuel == "electric" and f.roof == 2 and f.rejected_reason is None


def test_real_page_features_list_is_not_read_as_fuel():
    d = _real("73-932348")  # diesel dropside; features list says "Electric Windows"
    assert d.dealer == "Van Diesel"
    assert d.fuel_type == "diesel" and d.body_type == "dropside"
    assert "Electric Windows" not in (d.description or "")
    assert classify_title(d.classify_text()).rejected_reason == "diesel"


def test_dealer_with_london_number():
    html = "<h1>Van</h1><p>Contact the dealer Blackstone Motors Limited 020 3018 4583 * Get directions</p>"
    assert aa.parse_detail_page(html, "https://www.theaa.com/used-vans/cardetails/6-3370584").dealer \
        == "Blackstone Motors Limited"
