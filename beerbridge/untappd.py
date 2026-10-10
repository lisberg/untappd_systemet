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
