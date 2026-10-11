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


def fetch_user_beers(username: str, client_id=None, client_secret=None, access_token=None):
    """Distinct beers a user has checked in, via the Untappd v4 API.

    Needs credentials Untappd has approved for you (UNTAPPD_ACCESS_TOKEN, or
    UNTAPPD_CLIENT_ID + UNTAPPD_CLIENT_SECRET). Endpoint/shape written from the docs
    and wrappers; unverified here as untappd.com is unreachable from the build sandbox.
    """
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    access_token = access_token or os.environ.get("UNTAPPD_ACCESS_TOKEN")
    client_id = client_id or os.environ.get("UNTAPPD_CLIENT_ID")
    client_secret = client_secret or os.environ.get("UNTAPPD_CLIENT_SECRET")
    if access_token:
        auth = {"access_token": access_token}
    elif client_id and client_secret:
        auth = {"client_id": client_id, "client_secret": client_secret}
    else:
        raise RuntimeError("Set UNTAPPD_ACCESS_TOKEN or UNTAPPD_CLIENT_ID/UNTAPPD_CLIENT_SECRET")
    beers, offset = [], 0
    while True:
        qs = urllib.parse.urlencode({**auth, "limit": 50, "offset": offset})
        req = urllib.request.Request(
            f"https://api.untappd.com/v4/user/beers/{urllib.parse.quote(username)}?{qs}",
            headers={"User-Agent": "beerbridge (untappd-systembolaget)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                remaining = resp.headers.get("X-Ratelimit-Remaining")
                body = json.load(resp)["response"]["beers"]
        except urllib.error.HTTPError as e:
            hint = " (rate limit hit - keys get ~100 calls/hour; re-run later, use --untappd-cache)" if e.code == 429 else ""
            raise RuntimeError(f"Untappd API returned HTTP {e.code}{hint}") from e
        items = body.get("items", [])
        for it in items:
            name = it["beer"]["beer_name"]
            brewery = it.get("brewery", {}).get("brewery_name", "")
            beers.append(CheckedInBeer(name, brewery))
        if not items:
            return beers
        offset += len(items)
        if remaining is not None and int(remaining) <= 0:
            raise RuntimeError(f"Untappd rate limit exhausted after {len(beers)} beers; try again in an hour")


def save_cache(path, beers):
    Path(path).write_text(
        json.dumps([{"beer_name": b.name, "brewery_name": b.brewery} for b in beers], ensure_ascii=False),
        encoding="utf-8")
