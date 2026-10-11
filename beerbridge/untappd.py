"""Load an Untappd data export (JSON or CSV) into a list of checked-in beers."""
import csv
import json
from dataclasses import dataclass
from pathlib import Path

# Untappd's export has used slightly different column names over time.
_BEER = ("beer_name", "Beer Name", "beer")
_BREWERY = ("brewery_name", "Brewery Name", "brewery")


@dataclass(frozen=True)
class CheckedInBeer:
    name: str
    brewery: str


def _pick(row: dict, keys) -> str:
    for k in keys:
        v = row.get(k)
        if isinstance(v, dict):  # nested form: {"beer": {"beer_name": ...}}
            continue
        if v:
            return str(v).strip()
    return ""


def _flatten(row: dict) -> dict:
    flat = dict(row)
    for nested in ("beer", "brewery"):
        if isinstance(row.get(nested), dict):
            flat.update(row[nested])
    return flat


def load_export(path: str | Path) -> list[CheckedInBeer]:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):  # tolerate {"checkins": [...]}
            data = next((v for v in data.values() if isinstance(v, list)), [])
        rows = data
    else:
        rows = list(csv.DictReader(text.splitlines()))
    beers = {}
    for row in rows:
        row = _flatten(row)
        name, brewery = _pick(row, _BEER), _pick(row, _BREWERY)
        if name:
            beers[(name.lower(), brewery.lower())] = CheckedInBeer(name, brewery)
    return list(beers.values())


class RateLimited(RuntimeError):
    pass


class UntappdClient:
    """Minimal Untappd v4 client. Tracks the remaining hourly call budget.

    Credentials: UNTAPPD_ACCESS_TOKEN (user-authorised; needed for friend data), or
    UNTAPPD_CLIENT_ID + UNTAPPD_CLIENT_SECRET. UNTAPPD_API_BASE overrides the host (for testing).
    """

    def __init__(self, client_id=None, client_secret=None, access_token=None):
        import os

        access_token = access_token or os.environ.get("UNTAPPD_ACCESS_TOKEN")
        client_id = client_id or os.environ.get("UNTAPPD_CLIENT_ID")
        client_secret = client_secret or os.environ.get("UNTAPPD_CLIENT_SECRET")
        if access_token:
            self.auth = {"access_token": access_token}
        elif client_id and client_secret:
            self.auth = {"client_id": client_id, "client_secret": client_secret}
        else:
            raise RuntimeError("Set UNTAPPD_ACCESS_TOKEN or UNTAPPD_CLIENT_ID/UNTAPPD_CLIENT_SECRET")
        self.user_auth = bool(access_token)
        self.base = os.environ.get("UNTAPPD_API_BASE", "https://api.untappd.com/v4")
        self.remaining = None  # calls left this hour, from X-Ratelimit-Remaining

    def get(self, path, **params):
        import urllib.error
        import urllib.parse
        import urllib.request

        qs = urllib.parse.urlencode({**self.auth, **params})
        req = urllib.request.Request(f"{self.base}/{path}?{qs}",
                                     headers={"User-Agent": "beerbridge (untappd-systembolaget)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                rem = resp.headers.get("X-Ratelimit-Remaining")
                if rem is not None:
                    self.remaining = int(rem)
                return json.load(resp)["response"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self.remaining = 0
                raise RateLimited("Untappd rate limit hit (keys get ~100 calls/hour); try again later") from e
            raise RuntimeError(f"Untappd API returned HTTP {e.code}") from e


def fetch_user_beers(username: str, client_id=None, client_secret=None, access_token=None, client=None):
    """Distinct beers a user has checked in, via the Untappd v4 API (limit 50 per page)."""
    import urllib.parse

    client = client or UntappdClient(client_id, client_secret, access_token)
    beers, offset = [], 0
    while True:
        body = client.get(f"user/beers/{urllib.parse.quote(username)}", limit=50, offset=offset)["beers"]
        items = body.get("items", [])
        for it in items:
            beers.append(CheckedInBeer(it["beer"]["beer_name"], it.get("brewery", {}).get("brewery_name", "")))
        if not items:
            return beers
        offset += len(items)
        if client.remaining is not None and client.remaining <= 0:
            raise RateLimited(f"Untappd rate limit exhausted after {len(beers)} beers; try again in an hour")


def save_cache(path, beers):
    Path(path).write_text(
        json.dumps([{"beer_name": b.name, "brewery_name": b.brewery} for b in beers], ensure_ascii=False),
        encoding="utf-8")
