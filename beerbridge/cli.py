import argparse
import sys

from .match import score
from .systembolaget import fetch_store_beers, load_products_file, store_stock
from .untappd import fetch_user_beers, load_export


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
    ap.add_argument("export", nargs="?", help="Untappd export file (.json or .csv)")
    ap.add_argument("--untappd-user", help="Fetch check-ins via the Untappd API instead of an export file")
    ap.add_argument("--sb-bin", default="systembolaget", help="Path to the systembolaget-api CLI")
    ap.add_argument("--check-stock", action="store_true",
                    help="Also confirm shelf stock in the store (one extra call per untried beer)")
    ap.add_argument("--store", help="Systembolaget store id (siteId), e.g. 0102")
    ap.add_argument("--products-file", help="Use a saved product list instead of the live API")
    ap.add_argument("--threshold", type=float, default=0.8,
                    help="Match score at/above which a beer counts as checked in (default 0.8)")
    args = ap.parse_args(argv)

    if bool(args.store) == bool(args.products_file):
        ap.error("give exactly one of --store or --products-file")
    if bool(args.export) == bool(args.untappd_user):
        ap.error("give exactly one of an export file or --untappd-user")
    if args.check_stock and not args.store:
        ap.error("--check-stock needs --store")
    checked = load_export(args.export) if args.export else fetch_user_beers(args.untappd_user)
    products = (load_products_file(args.products_file) if args.products_file
                else list(fetch_store_beers(args.store, args.sb_bin)))
    todo = unchecked(products, checked, args.threshold)
    if args.check_stock:
        todo = [(p, n) for p, n in todo if store_stock(args.store, p.product_id, args.sb_bin) > 0]
    print(f"{len(products)} beers in store, {len(checked)} check-ins, {len(todo)} not yet tried\n",
          file=sys.stderr)
    for p, near in sorted(todo, key=lambda t: (t[0].style, t[0].producer, t[0].name)):
        price = f"{p.price:.0f} kr" if p.price else "-"
        print(f"{p.producer} - {p.name} | {p.style} | {price} | #{p.number}")


if __name__ == "__main__":
    main()
