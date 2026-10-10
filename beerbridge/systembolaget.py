"""Thin client for Systembolaget's unofficial web API.

NOTE: this is not a documented public API. Endpoint path, parameters and field
names below come from third-party descriptions and are UNVERIFIED; if
Systembolaget changes them, this is the only module that needs touching.
The subscription key is the public one the systembolaget.se site itself uses;
supply it via SYSTEMBOLAGET_API_KEY.
"""
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://api-extern.systembolaget.se/sb-api-ecommerce/v1"


@dataclass(frozen=True)
class Product:
    number: str
    name: str
    producer: str
    price: float | None
    volume_ml: int | None
    style: str


def _to_product(p: dict) -> Product:
    name = " ".join(x for x in (p.get("productNameBold"), p.get("productNameThin")) if x)
    return Product(
        number=str(p.get("productNumber", "")),
        name=name,
        producer=p.get("producerName") or "",
        price=p.get("price"),
        volume_ml=p.get("volume"),
        style=" / ".join(
            x for x in (p.get("categoryLevel2"), p.get("categoryLevel3")) if x
        ),
    )


def fetch_store_beers(store_id: str, api_key: str | None = None, page_size: int = 30):
    """Yield every beer product Systembolaget lists for the given store."""
    api_key = api_key or os.environ.get("SYSTEMBOLAGET_API_KEY")
    if not api_key:
        raise RuntimeError("Set SYSTEMBOLAGET_API_KEY (or pass --api-key)")
    page = 1
    while True:
        qs = urllib.parse.urlencode(
            {"storeId": store_id, "categoryLevel1": "Öl", "size": page_size, "page": page}
        )
        req = urllib.request.Request(
            f"{BASE}/productsearch/search?{qs}",
            headers={"Ocp-Apim-Subscription-Key": api_key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        for p in data.get("products", []):
            yield _to_product(p)
        nxt = data.get("metadata", {}).get("nextPage", -1)
        if nxt is None or nxt < 1 or nxt == page:
            return
        page = nxt


def load_products_file(path: str) -> list[Product]:
    """Load a saved/handmade list of raw API products (offline use and tests)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [_to_product(p) for p in (data["products"] if isinstance(data, dict) else data)]
