"""Fuzzy matching between Untappd beers and Systembolaget products."""
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

# Words that differ between the two catalogues without identifying a beer.
_NOISE = {
    "brewing", "brewery", "brewers", "bryggeri", "bryggerier", "bryggeriet",
    "co", "company", "ab", "ltd", "inc", "the", "beer", "ol", "ale",
}
# Style words: ignored when judging "one name contains the other".
_GENERIC = {
    "ipa", "dipa", "neipa", "tipa", "apa", "ipl", "pale", "lager", "stout", "porter", "imperial",
    "double", "triple", "hazy", "session", "india", "wheat", "sour", "gose", "pils", "pilsner",
    "saison", "dry", "hopped", "hop", "extra", "special", "edition", "batch", "barrel", "aged",
}
_YEAR = re.compile(r"^(19|20)\d\d$")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().replace("ø", "o").replace("æ", "ae"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(t for t in s.split() if t not in _NOISE and not _YEAR.match(t))


def _name_ratio(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    best = max(len(ta & tb) / len(ta | tb), SequenceMatcher(None, a, b).ratio())
    ga, gb = ta - _GENERIC, tb - _GENERIC  # "Fatamorgana" vs "Fatamorgana Imperial IPA"
    if ga and gb and (ga <= gb or gb <= ga):
        small = min(ga, gb, key=len)
        if len(small) >= 2 or max(len(t) for t in small) >= 5:
            best = max(best, 0.9)
    return best


def _brewery_ratio(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return max(len(ta & tb) / len(ta | tb), SequenceMatcher(None, a, b).ratio())


def _strip_tokens(name: str, words: set) -> str:
    """Drop brewery words from a beer name (either catalogue may prefix them)."""
    rest = " ".join(t for t in name.split() if t not in words)
    return rest or name


def score(name: str, brewery: str, sb_name: str, sb_producer: str) -> float:
    """0..1. The beer name matters most; brewery confirms or vetoes it."""
    b_norm, sb_b = normalize(brewery), normalize(sb_producer)
    brewery_words = set(b_norm.split()) | set(sb_b.split())
    a = _strip_tokens(normalize(name), brewery_words)
    c = _strip_tokens(normalize(sb_name), brewery_words)
    n = _name_ratio(a, c)
    if not b_norm or not sb_b:
        return n * 0.9
    b = _brewery_ratio(b_norm, sb_b)
    if b >= 0.5:
        return 0.7 * n + 0.3 * b
    # Producer may be a bottler/importer: trust a strong multi-word name match.
    if n >= 0.95 and len(a.split()) >= 2:
        return n * 0.85
    return min(n, b) * 0.8


class Matcher:
    """Index of check-ins so each product is only compared with plausible candidates."""

    def __init__(self, checked):
        self.checked = list(checked)
        self._index = defaultdict(list)
        for i, c in enumerate(self.checked):
            for t in set(normalize(f"{c.brewery} {c.name}").split()):
                self._index[t].append(i)

    def best(self, product):
        """(score, closest CheckedInBeer or None)."""
        cands = set()
        for t in set(normalize(f"{product.producer} {product.name}").split()):
            cands.update(self._index.get(t, ()))
        best, who = 0.0, None
        for i in cands:
            c = self.checked[i]
            s = score(c.name, c.brewery, product.name, product.producer)
            if s > best:
                best, who = s, c
        return best, who
