"""Systembolaget data via AlexGustafsson/systembolaget-api (the `systembolaget` CLI).

Install a release binary from https://github.com/AlexGustafsson/systembolaget-api
(it fetches the site's public API key itself) and put it on PATH, or pass --sb-bin.
`assortment` streams one JSON product per line; `stock` prints
{productId, storeId, shelf, stock, isInStoreAssortment}.
"""
import json
import subprocess
from dataclasses import dataclass

@dataclass(frozen=True)
class Product:
    number: str
    product_id: str
    name: str
    producer: str
    price: float | None
    volume_ml: int | None
    style: str


def _to_product(p: dict) -> Product:
    name = " ".join(x for x in (p.get("productNameBold"), p.get("productNameThin")) if x)
    return Product(
        number=str(p.get("productNumber", "")),
        product_id=str(p.get("productId") or p.get("productNumber", "")),
        name=name,
        producer=p.get("producerName") or "",
        price=p.get("price"),
        volume_ml=p.get("volume"),
        style=" / ".join(
            x for x in (p.get("categoryLevel2"), p.get("categoryLevel3")) if x
        ),
    )


def fetch_store_beers(store_id: str, binary: str = "systembolaget", page_delay: str = "250ms"):
    """Yield every beer in the store's assortment (streams the CLI's JSONL output)."""
    cmd = [binary, "assortment", "--category", "Öl", "--store", store_id, "--page-delay", page_delay]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8") as proc:
        for line in proc.stdout:
            if line.strip():
                yield _to_product(json.loads(line))
    if proc.returncode:
        raise RuntimeError(f"{binary} assortment exited with {proc.returncode}")


def store_stock(store_id: str, product_id: str, binary: str = "systembolaget") -> int:
    """Units on the shelf in the store (0 if not stocked)."""
    out = subprocess.run(
        [binary, "stock", "--store-id", store_id, "--product-id", product_id],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    data = json.loads(out)
    if isinstance(data, list):
        data = data[0] if data else {}
    return int(data.get("stock") or 0)


def load_products_file(path: str) -> list[Product]:
    """Load a saved/handmade list of raw API products (offline use and tests)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [_to_product(p) for p in (data["products"] if isinstance(data, dict) else data)]
