import unittest
from unittest.mock import patch
import src.harvest_bitbucket as hb

class TestHarvestBitbucket(unittest.TestCase):
    @patch('src.harvest_bitbucket.requests.get')
    def test_harvest_bitbucket(self, mock_get):
        mock_json = {
            "values": [
                {
                    "name": "repo1",
                    "full_name": "user/repo1",
                    "description": "Repo description",
                    "language": "python",
                    "created_on": "2022-01-01T00:00:00Z",
                    "updated_on": "2023-01-01T00:00:00Z",
                    "size": 12345,
                    "uuid": "{uuid}",
                    "links": {
                        "clone": [
                            {"href": "https://bitbucket.org/user/repo1.git", "name": "https"}
                        ]
                    }
                }
            ]
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_json
        results = hb.harvest_bitbucket('test query', max_results=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['name'], 'repo1')
        self.assertEqual(r['full_name'], 'user/repo1')
        self.assertEqual(r['description'], 'Repo description')
        self.assertEqual(r['language'], 'python')
        self.assertEqual(r['created_on'], '2022-01-01T00:00:00Z')
        self.assertEqual(r['updated_on'], '2023-01-01T00:00:00Z')
        self.assertEqual(r['size'], '12345')
        self.assertEqual(r['uuid'], '{uuid}')
        self.assertEqual(r['clone_links'], 'https://bitbucket.org/user/repo1.git')

if __name__ == '__main__':
    unittest.main()
