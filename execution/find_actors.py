import urllib.request
import json
import traceback

try:
    req = urllib.request.Request('https://api.apify.com/v2/actor-store/actors?search=linkedin%20comments', headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode())
    
    for item in data.get('data', {}).get('items', [])[:15]:
        print(f"{item.get('username')}/{item.get('name')} - {item.get('pricingModel')}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
