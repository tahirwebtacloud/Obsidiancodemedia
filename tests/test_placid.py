
import sys
import os
import requests
import json

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

try:
    from execution.placid_client import PlacidClient
except ImportError:
    print(f"Failed to import PlacidClient. sys.path is {sys.path}")
    sys.exit(1)

def test_carousel_generation():
    print(">>> Testing Placid Client (Full Carousel)...")
    
    test_slides = [
        {
            "type": "title",
            "data": {
                "headline": "Text Only Test", 
                "subheadline": "Verifying API without images"
            }
        },
        {
            "type": "content",
            "data": {
                "title": "Slide 2",
                "body": "No images here."
            }
        },
        {
            "type": "cta",
            "data": {
                "title": "Done",
                "subtitle": "Closing slide"
            }
        }
    ]
    
    client = PlacidClient()
    try:
        url = client.create_carousel(test_slides, filename="test_full_carousel.pdf")
        if url:
             print(f"SUCCESS: Carousel generated at: {url}")
        else:
             print("FAILURE: No URL returned (Timed out or Failed).")
             
    except Exception as e:
        print(f"FAILURE: Exception occurred: {e}")

if __name__ == "__main__":
    test_carousel_generation()
