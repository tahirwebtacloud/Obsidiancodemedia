import re
with open('duck.html', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()
links = set(re.findall(r'https://apify\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', text))
for link in links:
    print(link)
