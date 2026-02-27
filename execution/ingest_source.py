import os
import json
import argparse

def ingest_source(url, source_type):
    """
    Ingests content from YouTube, Blogs, or News.
    """
    print(f"Ingesting {source_type} from: {url}")
    
    # Mock extraction logic
    if source_type.lower() == "youtube":
        extracted_data = {
            "title": "Scaling AI in 2024",
            "transcript": "In this video, we discuss how AI is actually being used in real estate and finance. Most firms are failing because of paperwork...",
            "views": 50000
        }
    elif source_type.lower() == "blog":
        extracted_data = {
            "title": "The Obsidian Workflow for Founders",
            "content": "Obsidian is more than an app. It's a second brain. Here is how I use it to manage my LinkedIn system...",
            "author": "Obsidian Team"
        }
    else: # news
        extracted_data = {
            "headline": "New AI Regulations passed in EU",
            "summary": "The EU has finalized its AI act, impacting how companies deploy automation tools across the continent.",
            "source": "TechCrunch"
        }
    
    # Processed brief (Simulating LLM summarization)
    brief = {
        "source": url,
        "type": source_type,
        "key_insights": [
            "AI focus is shifting from generic use to solving specific 'PAIN'.",
            "Paperwork remains the biggest hurdle for automation adoption.",
            "Visual hooks are key for retention."
        ],
        "stats": ["90% reduction in comms", "70% less data entry"]
    }
    
    output_path = ".tmp/source_brief.json"
    os.makedirs(".tmp", exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(brief, f, indent=4)
    
    print(f"Source brief saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest content from various sources.")
    parser.add_argument("--url", required=True, help="URL of the source.")
    parser.add_argument("--type", required=True, choices=["youtube", "blog", "news"], help="Type of source.")
    
    args = parser.parse_args()
    ingest_source(args.url, args.type)
