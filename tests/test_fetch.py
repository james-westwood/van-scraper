import httpx
import pytest

from vanscraper import config
from vanscraper.fetch import PoliteClient, Robots, RobotsDisallowed

# Excerpt of the real https://www.theaa.com/robots.txt (fetched 2026-09-28).
# Keep the wildcards: urllib.robotparser ignored them and let the search through.
ROBOTS = """User-agent: *
Disallow: /search*
Disallow: /used-cars/displaycars*
Disallow: /used-cars/ajax_filter_values_dealer/
Disallow: *?*mymodelid=
Disallow: /used-cars/cardetails*
"""


def make_client(robots_status=200):
    requested = []

    def handler(request: httpx.Request):
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(robots_status, text=ROBOTS)
        return httpx.Response(200, text="<html>ok</html>")

    config.REQUEST_DELAY_S = 0
    return PoliteClient(httpx.Client(transport=httpx.MockTransport(handler))), requested


def test_disallowed_url_is_never_requested():
    pc, requested = make_client()
    with pytest.raises(RobotsDisallowed):
        pc.get("https://www.theaa.com/used-cars/displaycars?fueltype=electric")
    assert "/used-cars/displaycars" not in requested


def test_allowed_url_is_fetched():
    pc, _ = make_client()
    assert pc.get("https://www.theaa.com/used-vans/peugeot/boxer").status_code == 200


def test_robots_server_error_means_stay_out():
    pc, _ = make_client(robots_status=503)
    assert not pc.allowed("https://www.theaa.com/used-vans/peugeot/boxer")


def test_unreachable_robots_is_labelled_differently_from_disallowed():
    pc, _ = make_client(robots_status=503)
    with pytest.raises(RobotsDisallowed) as exc:
        pc.get("https://www.theaa.com/used-vans/peugeot/boxer")
    assert exc.value.reason == "robots_unreachable"
    pc2, _ = make_client()
    with pytest.raises(RobotsDisallowed) as exc2:
        pc2.get("https://www.theaa.com/used-cars/displaycars")
    assert exc2.value.reason == "disallowed"


@pytest.mark.parametrize("path, ok", [
    ("/used-cars/displaycars?fueltype=electric&classid=111&page=1", False),
    ("/used-cars/displaycars", False),
    ("/used-cars/cardetails/123", False),
    ("/used-vans/electric?mymodelid=5", False),
    ("/used-vans/electric", True),
    ("/used-vans/cardetails/168-152844", True),
    ("/used-vans/peugeot/boxer", True),
])
def test_real_aa_wildcard_rules(path, ok):
    assert Robots(ROBOTS.splitlines()).can_fetch(config.USER_AGENT, "https://www.theaa.com" + path) is ok


def test_dollar_anchor_and_allow_beats_equal_length_disallow():
    r = Robots(["User-agent: *", "Disallow: /*.pdf$", "Allow: /a", "Disallow: /a"])
    assert not r.can_fetch("x", "https://h/doc.pdf")
    assert r.can_fetch("x", "https://h/doc.pdf?v=1")
    assert r.can_fetch("x", "https://h/a")


def test_specific_agent_group_overrides_star():
    r = Robots(["User-agent: *", "Disallow: /", "", "User-agent: van-scraper", "Disallow: /private"])
    assert r.can_fetch("van-scraper/0.1 (x)", "https://h/public")
    assert not r.can_fetch("van-scraper/0.1 (x)", "https://h/private")
    assert not r.can_fetch("other", "https://h/public")
