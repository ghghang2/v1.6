import sys
sys.path.append('..')  # add repository root to PYTHONPATH
from app.tools.browser import browser
import json
print(browser('start'))
print(browser('navigate', url='https://www.nytimes.com'))
print(browser('wait_for', selector='h2'))
headlines_resp = browser('extract', selector='h2', mode='text', multiple=True)
headlines = json.loads(headlines_resp)['result']['result']
print('Headlines:', headlines[:5])
print(browser('stop'))
