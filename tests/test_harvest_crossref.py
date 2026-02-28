import unittest
from unittest.mock import patch
import src.harvest_crossref as hc

class TestHarvestCrossref(unittest.TestCase):
    @patch('src.harvest_crossref.requests.get')
    def test_harvest_crossref(self, mock_get):
        mock_json = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1234/example",
                        "title": ["Example Title"],
                        "author": [
                            {"given": "John", "family": "Doe"},
                            {"given": "Jane", "family": "Smith"}
                        ],
                        "issued": {"date-parts": [[2023]]},
                        "abstract": "Abstract text.",
                        "publisher": "Publisher X",
                        "URL": "https://doi.org/10.1234/example"
                    }
                ]
            }
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_json
        results = hc.harvest_crossref('test query', max_results=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['DOI'], '10.1234/example')
        self.assertEqual(r['title'], 'Example Title')
        self.assertEqual(r['authors'], 'John Doe, Jane Smith')
        self.assertEqual(r['issued'], '2023')
        self.assertEqual(r['abstract'], 'Abstract text.')
        self.assertEqual(r['publisher'], 'Publisher X')
        self.assertEqual(r['URL'], 'https://doi.org/10.1234/example')

if __name__ == '__main__':
    unittest.main()
