import argparse
import sys

from .match import score
from .systembolaget import fetch_store_beers, load_products_file
from .untappd import load_export


def unchecked(products, checked, threshold=0.8):
    """Products with no sufficiently similar beer in the check-in history."""
    out = []
    for p in products:
        best = max((score(c.name, c.brewery, p.name, p.producer) for c in checked), default=0)
        if best < threshold:
            out.append((p, best))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", help="Untappd export file (.json or .csv)")
    ap.add_argument("--store", help="Systembolaget store id (siteId), e.g. 0102")
    ap.add_argument("--products-file", help="Use a saved product list instead of the live API")
    ap.add_argument("--api-key", help="Defaults to $SYSTEMBOLAGET_API_KEY")
    ap.add_argument("--threshold", type=float, default=0.8,
                    help="Match score at/above which a beer counts as checked in (default 0.8)")
    args = ap.parse_args(argv)

    if bool(args.store) == bool(args.products_file):
        ap.error("give exactly one of --store or --products-file")
    checked = load_export(args.export)
    products = (load_products_file(args.products_file) if args.products_file
                else list(fetch_store_beers(args.store, args.api_key)))
    todo = unchecked(products, checked, args.threshold)
    print(f"{len(products)} beers in store, {len(checked)} check-ins, {len(todo)} not yet tried\n",
          file=sys.stderr)
    for p, near in sorted(todo, key=lambda t: (t[0].style, t[0].producer, t[0].name)):
        price = f"{p.price:.0f} kr" if p.price else "-"
        print(f"{p.producer} - {p.name} | {p.style} | {price} | #{p.number}")


if __name__ == "__main__":
    main()
