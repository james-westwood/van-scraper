"""HTTP with manners: robots.txt checked per URL, per-host delay, honest UA.

A URL disallowed by robots.txt raises RobotsDisallowed and is never
requested. That's deliberate: a scraper that ignores robots.txt gets
blocked, and a silently-blocked scraper looks exactly like "no vans this
week". Better to fail loudly and visibly in run_metadata.
"""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

from . import config


class RobotsDisallowed(Exception):
    """reason: 'disallowed' (site says no) or 'robots_unreachable' (couldn't
    read robots.txt, so we stayed out -- a network problem, not a site rule)."""

    def __init__(self, url: str, reason: str = "disallowed"):
        super().__init__(f"{reason}: {url}")
        self.reason = reason


class PoliteClient:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.TIMEOUT_S,
            follow_redirects=True,
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._robots_ok: dict[str, bool] = {}
        self._last_hit: dict[str, float] = {}

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            self._robots_ok[origin] = True
            try:
                r = self.client.get(f"{origin}/robots.txt")
                # No robots.txt (404) means everything is allowed; a server
                # error means we can't know, so be conservative and disallow.
                if r.status_code == 404:
                    rp.parse([])
                elif r.status_code >= 400:
                    rp.parse(["User-agent: *", "Disallow: /"])
                    self._robots_ok[origin] = False
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp.parse(["User-agent: *", "Disallow: /"])
                self._robots_ok[origin] = False
            self._robots[origin] = rp
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(config.USER_AGENT, url)

    def get(self, url: str) -> httpx.Response:
        if not self.allowed(url):
            origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
            reason = "disallowed" if self._robots_ok.get(origin) else "robots_unreachable"
            raise RobotsDisallowed(url, reason)
        host = urlsplit(url).netloc
        wait = config.REQUEST_DELAY_S - (time.monotonic() - self._last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        resp = self.client.get(url)
        self._last_hit[host] = time.monotonic()
        return resp
