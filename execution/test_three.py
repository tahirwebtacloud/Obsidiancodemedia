import os
from dotenv import load_dotenv
from apify_client import ApifyClient
import json

load_dotenv()
client = ApifyClient(os.getenv('APIFY_API_KEY'))

try:
    run = client.actor('bhansalisoft/linkedin-post-comments-scraper').call(
        run_input={
            'url': 'https://www.linkedin.com/posts/keithmortier_the-hardest-working-person-in-the-room-is-activity-7424897669300400128-X72L',
            'postUrl': 'https://www.linkedin.com/posts/keithmortier_the-hardest-working-person-in-the-room-is-activity-7424897669300400128-X72L',
            'startUrls': [{'url': 'https://www.linkedin.com/posts/keithmortier_the-hardest-working-person-in-the-room-is-activity-7424897669300400128-X72L'}],
            'maxItems': 2
        }
    )
    items = list(client.dataset(run['defaultDatasetId']).iterate_items())
    if items:
        print(json.dumps(items[0], indent=2))
    else:
        print("No items returned")
except Exception as e:
    print(f"Error calling bhansalisoft/linkedin-post-comments-scraper: {e}")
