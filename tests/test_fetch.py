import httpx
import pytest

from vanscraper import config
from vanscraper.fetch import PoliteClient, RobotsDisallowed

ROBOTS = "User-agent: *\nDisallow: /used-cars/displaycars\n"


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
