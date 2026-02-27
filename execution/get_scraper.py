from ddgs import DDGS
import re
results = DDGS().text('site:apify.com "linkedin comments scraper"', max_results=15)
for r in results:
    url = r.get('href', '')
    if 'apify.com' in url and '/linkedin' in url:
        print(url)
