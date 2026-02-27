import os
from dotenv import load_dotenv
from apify_client import ApifyClient
import json
import traceback

load_dotenv()
client = ApifyClient(os.getenv('APIFY_API_KEY'))

print("Testing Apimaestro...")
try:
    run = client.actor('apimaestro/linkedin-post-comments-replies-engagements-scraper-no-cookies').call(
        run_input={
            'postIds': ['7424897669300400128']
        }
    )
    items = list(client.dataset(run['defaultDatasetId']).iterate_items())
    if items:
        print(json.dumps(items[0], indent=2))
        with open('apimaestro_out.json', 'w') as f:
            json.dump(items, f, indent=2)
    else:
        print("No items returned")
except Exception as e:
    print(f"Error calling apimaestro: {e}")

print("-" * 50)
print("Testing FreshData...")

try:
    run = client.actor('freshdata/linkedin-post-comments-scraper').call(
        run_input={
            'urn': 'urn:li:activity:7424897669300400128',
            'maxComments': 2
        }
    )
    items = list(client.dataset(run['defaultDatasetId']).iterate_items())
    if items:
        print(json.dumps(items[0], indent=2))
        with open('freshdata_out.json', 'w') as f:
            json.dump(items, f, indent=2)
    else:
        print("No items returned")
except Exception as e:
    print(f"Error calling freshdata: {e}")
