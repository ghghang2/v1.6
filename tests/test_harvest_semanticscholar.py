import unittest
from unittest.mock import patch
import src.harvest_semanticscholar as hss

class TestHarvestSemanticScholar(unittest.TestCase):
    @patch('src.harvest_semanticscholar.requests.get')
    def test_harvest_semanticscholar(self, mock_get):
        mock_response = {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Paper Title",
                    "authors": [{"name": "Alice"}, {"name": "Bob"}],
                    "year": 2023,
                    "abstract": "Abstract text.",
                    "venue": "Conference X",
                    "referenceCount": 5,
                    "citationCount": 10,
                }
            ]
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response
        results = hss.harvest_semanticscholar('test query', max_results=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['paperId'], 'abc123')
        self.assertEqual(r['title'], 'Paper Title')
        self.assertEqual(r['authors'], 'Alice, Bob')
        self.assertEqual(r['year'], '2023')
        self.assertEqual(r['abstract'], 'Abstract text.')
        self.assertEqual(r['venue'], 'Conference X')
        self.assertEqual(r['referenceCount'], '5')
        self.assertEqual(r['citationCount'], '10')

if __name__ == '__main__':
    unittest.main()
