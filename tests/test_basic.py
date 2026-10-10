import json
import tempfile
import unittest
from pathlib import Path

from beerbridge.cli import unchecked
from beerbridge.match import score
from beerbridge.systembolaget import Product, load_products_file
from beerbridge.untappd import load_export


def P(name, producer):
    return Product("1", "1", name, producer, 30.0, 330, "Ale")


class Tests(unittest.TestCase):
    def test_same_beer_despite_naming_differences(self):
        self.assertGreater(score("Stockholm Calling", "Omnipollo", "Stockholm Calling", "Omnipollo Bryggeri AB"), 0.9)
        self.assertGreater(score("Älg IPA", "Nils Oscar Brewery", "Älg IPA", "Nils Oscar"), 0.85)

    def test_different_beers_same_brewery_not_matched(self):
        self.assertLess(score("Hazy IPA", "Omnipollo", "Fatamorgana", "Omnipollo"), 0.6)

    def test_unchecked_filters(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "e.csv").write_text("beer_name,brewery_name\nFatamorgana,Omnipollo\n")
        checked = load_export(tmp / "e.csv")
        res = unchecked([P("Fatamorgana", "Omnipollo"), P("Nebuchadnezzar", "Omnipollo")], checked)
        self.assertEqual([p.name for p, _ in res], ["Nebuchadnezzar"])

    def test_json_export_and_products_file(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "e.json").write_text(json.dumps([{"beer": {"beer_name": "X"}, "brewery": {"brewery_name": "Y"}}]))
        self.assertEqual(load_export(tmp / "e.json")[0].brewery, "Y")
        (tmp / "p.json").write_text(json.dumps({"products": [
            {"productNumber": 5, "productNameBold": "Foo", "productNameThin": "Bar", "producerName": "Baz"}]}))
        self.assertEqual(load_products_file(str(tmp / "p.json"))[0].name, "Foo Bar")


if __name__ == "__main__":
    unittest.main()
