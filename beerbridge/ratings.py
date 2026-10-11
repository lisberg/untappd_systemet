"""Untappd ratings for Systembolaget products.

Untappd allows ~100 calls/hour per key and a lookup costs ~2 (search + info), so ratings are fetched
on demand by a background worker, throttled to the remaining budget, and cached on disk.
"""
import json
import threading
import time
from pathlib import Path

from .match import score
from .untappd import RateLimited

MIN_MATCH = 0.6
RETRY_AFTER = 30 * 86400  # re-check a cached entry after 30 days


def lookup(client, product) -> dict:
    """Find the product on Untappd and return {found, bid, score, count}."""
    res = client.get("search/beer", q=f"{product.producer} {product.name}".strip(), limit=5)
    items = res.get("beers", {}).get("items", [])
    best, best_s = None, 0.0
    for it in items:
        s = score(it["beer"]["beer_name"], it.get("brewery", {}).get("brewery_name", ""),
                  product.name, product.producer)
        if s > best_s:
            best, best_s = it, s
    entry = {"ts": time.time(), "found": False}
    if not best or best_s < MIN_MATCH:
        return entry
    bid = best["beer"]["bid"]
    beer = client.get(f"beer/info/{bid}")["beer"]
    entry.update(found=True, bid=bid, name=beer.get("beer_name"), score=beer.get("rating_score"),
                 count=beer.get("rating_count"))
    return entry


class RatingStore:
    def __init__(self, client, path=".ratings-cache.json", pause=0.5):
        self.client, self.path, self.pause = client, Path(path), pause
        self.lock = threading.Lock()
        self.queue = []  # products waiting
        self.paused = ""
        self.worker = None
        try:
            self.cache = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def enqueue(self, products):
        now = time.time()
        with self.lock:
            queued = {p.number for p in self.queue}
            for p in products:
                c = self.cache.get(p.number)
                if p.number not in queued and not (c and now - c.get("ts", 0) < RETRY_AFTER):
                    self.queue.append(p)
            self.paused = ""
            if self.queue and not (self.worker and self.worker.is_alive()):
                self.worker = threading.Thread(target=self._run, daemon=True)
                self.worker.start()

    def _run(self):
        while True:
            with self.lock:
                if not self.queue:
                    return
                p = self.queue[0]
            try:
                entry = lookup(self.client, p)
            except RateLimited as e:
                with self.lock:
                    self.paused = str(e)
                return  # queue kept; the next enqueue() resumes
            except Exception as e:  # a bad response for one beer shouldn't stall the rest
                entry = {"ts": time.time(), "found": False, "error": str(e)}
            with self.lock:
                self.cache[p.number] = entry
                self.queue.pop(0)
                self._save()
            if self.client.remaining is not None and self.client.remaining <= 1:
                with self.lock:
                    self.paused = "Out of Untappd API calls for this hour; will resume when you queue again."
                return
            time.sleep(self.pause)

    def snapshot(self):
        with self.lock:
            return {
                "ratings": dict(self.cache),
                "status": {"enabled": True, "pending": len(self.queue), "paused": self.paused,
                           "remaining": self.client.remaining},
            }
