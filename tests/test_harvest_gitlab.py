import unittest
from unittest.mock import patch
import src.harvest_gitlab as hg

class TestHarvestGitlab(unittest.TestCase):
    @patch('src.harvest_gitlab.requests.get')
    def test_harvest_gitlab(self, mock_get):
        mock_json = [
            {
                "id": 123,
                "name": "test-repo",
                "description": "A test repo",
                "web_url": "https://gitlab.com/user/test-repo",
                "ssh_url_to_repo": "git@gitlab.com:user/test-repo.git",
                "visibility": "public",
                "star_count": 10,
                "forks_count": 2,
                "last_activity_at": "2023-01-01T00:00:00Z"
            }
        ]
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_json
        results = hg.harvest_gitlab('test query', max_results=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['id'], '123')
        self.assertEqual(r['name'], 'test-repo')
        self.assertEqual(r['description'], 'A test repo')
        self.assertEqual(r['web_url'], 'https://gitlab.com/user/test-repo')
        self.assertEqual(r['ssh_url_to_repo'], 'git@gitlab.com:user/test-repo.git')
        self.assertEqual(r['visibility'], 'public')
        self.assertEqual(r['star_count'], '10')
        self.assertEqual(r['forks_count'], '2')
        self.assertEqual(r['last_activity_at'], '2023-01-01T00:00:00Z')

if __name__ == '__main__':
    unittest.main()
