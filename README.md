# untappd-systembolaget

Lists the beers stocked in a given Systembolaget store that you have **not** yet checked in on Untappd.

```
# one-time: download a `systembolaget` release binary from
# https://github.com/AlexGustafsson/systembolaget-api and put it on PATH (or use --sb-bin)

python3 -m beerbridge my_untappd_export.json --store 0102              # export file
python3 -m beerbridge --untappd-user myname --store 0102 --check-stock  # Untappd API + shelf stock
python3 -m beerbridge export.csv --products-file saved_products.json    # offline
python3 -m unittest discover -s tests -t .
```

## Web UI (phone-friendly)
```
python3 -m beerbridge.web --untappd-user myname                  # http://127.0.0.1:8000
python3 -m beerbridge.web export.json --host 0.0.0.0 --port 8000  # open from your phone on the same Wi-Fi
```
Search for a store, tap it, then filter/sort the untried beers; "Only confirmed in stock" adds the per-beer stock
check (slower). The chosen store is remembered in the browser, and each store's assortment is cached for an hour.
Credentials stay on the server. There is no authentication, so only expose it on a network you trust.

## How it works
1. **Untappd** - either your own data export (Account settings > Exportable Data; JSON/CSV), or the
   [Untappd v4 API](https://untappd.com/api/docs) (`--untappd-user`, needs `UNTAPPD_ACCESS_TOKEN` or
   `UNTAPPD_CLIENT_ID` + `UNTAPPD_CLIENT_SECRET`; Untappd has to have approved your app).
2. **Systembolaget** - shells out to [systembolaget-api](https://github.com/AlexGustafsson/systembolaget-api):
   `assortment --category Öl --store ID` for the store's beers (JSONL), and with `--check-stock`
   `stock --store-id ID --product-id N` per untried beer to keep only those with shelf stock > 0.
3. **Matching** - `beerbridge/match.py` normalises names (accents, "Brewing"/"Bryggeri" etc.) and fuzzy-matches
   beer name and brewery. Anything scoring below `--threshold` (default 0.8) is reported as not yet tried.

## Caveats
- Neither live service could be reached from the build sandbox. The `systembolaget` CLI path is tested only against a
  stand-in script emitting the documented JSON shapes; the Untappd API call is unverified. Product JSON keys
  (`productNumber`, `productId`, `producerName`, ...) may need small tweaks in `systembolaget.py` on first real run.
- The store-search response keys (`siteId`, `alias`, `city`) are guesses, same as the product keys; the UI tolerates a few variants.
- `--check-stock` makes one call per untried beer; run it without first to see the (larger) assortment list.
- Fuzzy matching will produce some false positives/negatives; tune `--threshold`.
