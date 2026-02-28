import unittest
from unittest.mock import patch
import src.harvest_patents as hp

class TestHarvestPatents(unittest.TestCase):
    @patch('src.harvest_patents.requests.post')
    def test_harvest_patents(self, mock_post):
        mock_json = {
            "patents": [
                {
                    "patent_number": "US1234567",
                    "patent_title": "Sample Patent Title",
                    "inventor": [
                        {"inventor_name": "Alice"},
                        {"inventor_name": "Bob"}
                    ],
                    "assignee": [
                        {"assignee_name": "Acme Corp"}
                    ],
                    "inventor_city": "City",
                    "inventor_state": "State",
                    "inventor_country": "Country",
                    "patent_abstract": "Patent abstract.",
                    "patent_date_filed": "2022-01-01",
                    "patent_date_publication": "2023-01-01"
                }
            ]
        }
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_json
        results = hp.harvest_patents('test query', max_results=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['patent_number'], 'US1234567')
        self.assertEqual(r['title'], 'Sample Patent Title')
        self.assertEqual(r['inventors'], 'Alice, Bob')
        self.assertEqual(r['assignees'], 'Acme Corp')
        self.assertEqual(r['inventor_city'], 'City')
        self.assertEqual(r['inventor_state'], 'State')
        self.assertEqual(r['inventor_country'], 'Country')
        self.assertEqual(r['abstract'], 'Patent abstract.')
        self.assertEqual(r['date_filed'], '2022-01-01')
        self.assertEqual(r['date_publication'], '2023-01-01')

if __name__ == '__main__':
    unittest.main()
