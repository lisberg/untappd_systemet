"""Fuzzy matching between Untappd beers and Systembolaget products."""
import re
import unicodedata
from difflib import SequenceMatcher

# Words that differ between the two catalogues without identifying a beer.
_NOISE = {
    "brewing", "brewery", "brewers", "bryggeri", "bryggerier", "bryggeriet",
    "co", "company", "ab", "ltd", "inc", "the", "beer", "ol", "ale",
}


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().replace("ø", "o").replace("æ", "ae"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(t for t in s.split() if t not in _NOISE)


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    jacc = len(ta & tb) / len(ta | tb)
    return max(jacc, SequenceMatcher(None, a, b).ratio())


def _strip(name: str, brewery: str) -> str:
    """Drop brewery words from a beer name (one catalogue often prefixes them)."""
    bw = set(brewery.split())
    rest = " ".join(t for t in name.split() if t not in bw)
    return rest or name


def score(name: str, brewery: str, sb_name: str, sb_producer: str) -> float:
    """0..1. The beer name matters most; brewery confirms or vetoes it."""
    b_norm, sb_b_norm = normalize(brewery), normalize(sb_producer)
    n = _ratio(_strip(normalize(name), b_norm), _strip(normalize(sb_name), sb_b_norm))
    if not b_norm or not sb_b_norm:
        return n * 0.9
    b = _ratio(b_norm, sb_b_norm)
    return 0.7 * n + 0.3 * b if b >= 0.5 else min(n, b) * 0.8
