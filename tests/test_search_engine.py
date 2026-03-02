import unittest
from unittest.mock import patch, MagicMock
import src.search_engine as se

class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        # Prepare a minimal DuckDuckGo HTML snippet with two results
        self.sample_html = """
        <html>
            <body>
                <div class=\"result\">
                    <a class=\"result__a\" href=\"https://example.com/paper1\">Paper 1 Title</a>
                    <a class=\"result__a\" href=\"https://example.com/paper1\">Paper 1 Title</a>
                    <a class=\"result__snippet\">Snippet 1</a>
                </div>
                <div class=\"result\">
                    <a class=\"result__a\" href=\"https://example.com/paper2\">Paper 2 Title</a>
                    <a class=\"result__a\" href=\"https://example.com/paper2\">Paper 2 Title</a>
                    <a class=\"result__snippet\">Snippet 2</a>
                </div>
            </body>
        </html>
        """

    @patch('src.search_engine.browser')
    def test_perform_search(self, mock_browser):
        # Mock browser to return our sample HTML
        mock_browser.return_value = {'text': self.sample_html}
        results = se.perform_search('test query', num_results=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['title'], 'Paper 1 Title')
        self.assertEqual(results[0]['url'], 'https://example.com/paper1')
        self.assertEqual(results[0]['snippet'], 'Snippet 1')
        self.assertEqual(results[1]['title'], 'Paper 2 Title')
        self.assertEqual(results[1]['url'], 'https://example.com/paper2')
        self.assertEqual(results[1]['snippet'], 'Snippet 2')

if __name__ == '__main__':
    unittest.main()