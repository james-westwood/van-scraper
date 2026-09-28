"""HTTP with manners: robots.txt checked per URL, per-host delay, honest UA.

A URL disallowed by robots.txt raises RobotsDisallowed and is never
requested. That's deliberate: a scraper that ignores robots.txt gets
blocked, and a silently-blocked scraper looks exactly like "no vans this
week". Better to fail loudly and visibly in run_metadata.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

import httpx

from . import config


class RobotsDisallowed(Exception):
    """reason: 'disallowed' (site says no) or 'robots_unreachable' (couldn't
    read robots.txt, so we stayed out -- a network problem, not a site rule)."""

    def __init__(self, url: str, reason: str = "disallowed"):
        super().__init__(f"{reason}: {url}")
        self.reason = reason


class Robots:
    """robots.txt rules per RFC 9309, including the `*` and `$` wildcards.

    urllib.robotparser treats `*` literally, so AA's
    `Disallow: /used-cars/displaycars*` silently allowed the search page.
    """

    def __init__(self, lines: list[str]):
        # Groups of (agents, rules); consecutive User-agent lines share a group.
        self._groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[bool, str]] = []
        for raw in lines:
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, val = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if rules:
                    self._groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(val.lower())
            elif key in ("allow", "disallow") and agents:
                if val:  # empty Disallow means allow everything
                    rules.append((key == "allow", val))
        if agents:
            self._groups.append((agents, rules))

    def _rules_for(self, user_agent: str) -> list[tuple[bool, str]]:
        token = user_agent.split("/", 1)[0].strip().lower()
        specific = [r for a, rs in self._groups if token in a for r in rs]
        if any(token in a for a, _ in self._groups):
            return specific
        return [r for a, rs in self._groups if "*" in a for r in rs]

    @staticmethod
    def _matches(pattern: str, path: str) -> bool:
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        regex = ".*".join(re.escape(part) for part in body.split("*"))
        return re.match(regex + ("$" if anchored else ""), path) is not None

    def can_fetch(self, user_agent: str, url: str) -> bool:
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best: tuple[int, bool] | None = None  # (pattern length, allow)
        for allow, pattern in self._rules_for(user_agent):
            if self._matches(pattern, path):
                # Longest match wins; on a tie, Allow wins.
                cand = (len(pattern), allow)
                if best is None or cand > best:
                    best = cand
        return best is None or best[1]


class PoliteClient:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.TIMEOUT_S,
            follow_redirects=True,
        )
        self._robots: dict[str, Robots] = {}
        self._robots_ok: dict[str, bool] = {}
        self._last_hit: dict[str, float] = {}

    def _robots_for(self, url: str) -> Robots:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots_ok[origin] = True
            try:
                r = self.client.get(f"{origin}/robots.txt")
                # No robots.txt (404) means everything is allowed; a server
                # error means we can't know, so be conservative and disallow.
                if r.status_code == 404:
                    rp = Robots([])
                elif r.status_code >= 400:
                    rp = Robots(["User-agent: *", "Disallow: /"])
                    self._robots_ok[origin] = False
                else:
                    rp = Robots(r.text.splitlines())
            except httpx.HTTPError:
                rp = Robots(["User-agent: *", "Disallow: /"])
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
