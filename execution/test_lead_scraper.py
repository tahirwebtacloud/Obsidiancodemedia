import os
from dotenv import load_dotenv
import lead_scraper
import json

load_dotenv()

# We use the same post URL that we used previously
test_urls = ["https://www.linkedin.com/posts/keithmortier_the-hardest-working-person-in-the-room-is-activity-7424897669300400128-X72L"]
print("Running run_lead_scan with the new comments scraper...")
result = lead_scraper.run_lead_scan(post_urls=test_urls)

with open('test_lead_scan_result.json', 'w') as f:
    json.dump(result, f, indent=2)

leads_with_comments = [l for l in result.get('leads', []) if "comment" in l.get('interaction_type', '')]
print(f"Found {len(leads_with_comments)} leads with comments out of {len(result.get('leads', []))} total.")
for l in leads_with_comments[:3]:
    print(f"Name: {l.get('name')}, Type: {l.get('interaction_type')}")
    print(f"Comment: {l.get('text')}\n")
