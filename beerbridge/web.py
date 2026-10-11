"""Tiny mobile-friendly web UI: pick a store, see beers you haven't checked in.

    python3 -m beerbridge.web --untappd-user NAME            # http://127.0.0.1:8000
    python3 -m beerbridge.web export.json --host 0.0.0.0     # reachable from your phone on the LAN

There is no authentication; only expose it on a network you trust.
"""
import argparse
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .cli import unchecked
from .systembolaget import fetch_store_beers, store_stock
from .untappd import fetch_user_beers, load_export, save_cache

ASSORTMENT_TTL = 3600
PAGE = Path(__file__).with_name("index.html")


class App:
    def __init__(self, checked, sb_bin, threshold):
        self.checked, self.sb_bin, self.threshold = checked, sb_bin, threshold
        self._assortment = {}  # store -> (time, products)
        self._lock = threading.Lock()

    def stores(self, query):
        out = subprocess.run([self.sb_bin, "stores", "--search", query], capture_output=True,
                             text=True, encoding="utf-8", check=True).stdout.strip()
        rows = json.loads(out) if out.startswith("[") else [json.loads(l) for l in out.splitlines() if l.strip()]
        return [{
            "id": str(r.get("siteId") or r.get("storeId") or r.get("id") or ""),
            "name": r.get("displayName") or r.get("alias") or r.get("name") or "",
            "city": r.get("city") or "",
        } for r in rows][:25]

    def products(self, store):
        with self._lock:  # one fetch per store at a time; the CLI is rate-polite and slow
            hit = self._assortment.get(store)
            if not hit or time.time() - hit[0] > ASSORTMENT_TTL:
                hit = (time.time(), list(fetch_store_beers(store, self.sb_bin)))
                self._assortment[store] = hit
            return hit[1]

    def untried(self, store, check_stock):
        todo = unchecked(self.products(store), self.checked, self.threshold)
        if check_stock:
            with ThreadPoolExecutor(4) as pool:
                stock = list(pool.map(lambda t: store_stock(store, t[0].product_id, self.sb_bin), todo))
            todo = [(p, n) for (p, n), s in zip(todo, stock) if s > 0]
        return [{"producer": p.producer, "name": p.name, "style": p.style, "price": p.price,
                 "volume": p.volume_ml, "number": p.number} for p, _ in todo]


def make_handler(app):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/":
                    self._send(200, PAGE.read_bytes(), "text/html")
                elif u.path == "/api/stores":
                    self._send(200, app.stores(q.get("q", "")))
                elif u.path == "/api/untried" and q.get("store", "").isalnum():
                    self._send(200, {"checked": len(app.checked),
                                     "beers": app.untried(q["store"], q.get("stock") == "1")})
                else:
                    self._send(404, {"error": "not found"})
            except Exception as e:  # surface CLI/API failures to the page
                self._send(502, {"error": str(e)})

        def log_message(self, *a):
            pass
    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", nargs="?", help="Untappd export file (.json or .csv)")
    ap.add_argument("--untappd-user")
    ap.add_argument("--untappd-cache", default=".untappd-cache.json")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--sb-bin", default="systembolaget")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    if bool(a.export) == bool(a.untappd_user):
        ap.error("give exactly one of an export file or --untappd-user")
    if a.export:
        checked = load_export(a.export)
    elif Path(a.untappd_cache).exists() and not a.refresh:
        checked = load_export(a.untappd_cache)
    else:
        checked = fetch_user_beers(a.untappd_user)
        save_cache(a.untappd_cache, checked)
    print(f"{len(checked)} check-ins loaded; serving on http://{a.host}:{a.port}")
    ThreadingHTTPServer((a.host, a.port), make_handler(App(checked, a.sb_bin, a.threshold))).serve_forever()


if __name__ == "__main__":
    main()
