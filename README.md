# untappd-systembolaget

Lists the beers stocked in a given Systembolaget store that you have **not** yet checked in on Untappd.

```
export SYSTEMBOLAGET_API_KEY=...            # see below
python3 -m beerbridge my_untappd_export.json --store 0102
python3 -m beerbridge export.csv --products-file saved_products.json   # offline
python3 -m unittest discover -s tests -t .
```

## How it works
1. **Untappd side** - Untappd has no usable public API, so the app reads your own data export
   (Account settings > Exportable Data; JSON or CSV). Eligibility has changed over time, so check Untappd's settings page.
2. **Systembolaget side** - `beerbridge/systembolaget.py` pages through the beers listed for a store
   via Systembolaget's unofficial web API, using the public key the systembolaget.se site uses.
3. **Matching** - `beerbridge/match.py` normalises names (accents, "Brewing"/"Bryggeri" etc.) and fuzzy-matches
   beer name and brewery. Anything scoring below `--threshold` (default 0.8) is reported as not yet tried.

## Caveats
- The Systembolaget endpoint, parameters and field names are **unverified** (written from third-party descriptions;
  the build sandbox could not reach the host). Expect to adjust that one module on first real run.
- "Listed for the store" may be assortment rather than live stock; check Systembolaget's stock endpoint if you need that.
- Fuzzy matching will produce some false positives/negatives; tune `--threshold`.
