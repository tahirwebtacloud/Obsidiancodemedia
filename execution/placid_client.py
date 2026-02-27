
import requests
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

class PlacidClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("PLACID_API_KEY", "")
        self.base_url = "https://api.placid.app/api/rest"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Placid-Python-Client/1.0"
        }
        
        # Template Configuration
        self.templates = {
            "design1": {
                "title": "bxoye2pmubwql",
                "content": "5rqbeudgt7cml",
                "cta": "d33hiaf7tcp0k"
            },
            "design2": {
                "title": "9xoue4sjxupjo",
                "content": "5lu4ppzpa8ul9",
                "cta": "7mdqtojzjaibw"
            }
        }

    def create_carousel(self, slides_data, filename="carousel.pdf", design="design1"):
        """
        Generates a PDF carousel from a list of slide data objects.
        """
        
        if design not in self.templates:
            print(f"Warning: Design '{design}' not found. Defaulting to design1.")
            design = "design1"
            
        template_ids = self.templates[design]
        pages = []
        
        for slide in slides_data:
            slide_type = slide.get("type", "").lower()
            data = slide.get("data", {})
            
            if slide_type not in template_ids:
                print(f"Skipping unknown slide type: {slide_type}")
                continue
                
            template_uuid = template_ids[slide_type]
            layers = {}
            
            # MAP DATA TO LAYERS BASED ON DESIGN
            if design == "design1":
                if slide_type == "title":
                    layers["Title"] = {"text": data.get("headline", "")}
                    layers["subtitle"] = {"text": data.get("subheadline", "")}
                    if data.get("image"):
                        layers["New picture layer"] = {
                            "media": data.get("image"),
                            "link_target": "<br>" # FIX: Required by template
                        }
                        
                elif slide_type == "content":
                    layers["title"] = {"text": data.get("title", "")}
                    layers["body"] = {"text": data.get("body", "")}
                    if data.get("image"):
                        layers["image"] = {"media": data.get("image")}
                        
                elif slide_type == "cta":
                    layers["cta title"] = {"text": data.get("title", "Follow for more")}
                    layers["ahort closing line"] = {"text": data.get("subtitle", "")}
                    if data.get("image_large"):
                        layers["img large"] = {"media": data.get("image_large")}
                    if data.get("image_small"):
                        layers["img small"] = {"media": data.get("image_small")}

            elif design == "design2":
                 if slide_type == "title":
                    layers["New text layer"] = {"text": data.get("headline", "")}
                    if data.get("image"):
                        layers["New picture layer"] = {"media": data.get("image")}

                 elif slide_type == "content":
                    layers["New text layer"] = {"text": str(data.get("number", "1."))} 
                    layers["New text layer-1"] = {"text": data.get("title", "")}
                    layers["New text layer-2"] = {"text": data.get("body", "")}

                 elif slide_type == "cta":
                    layers["New text layer"] = {"text": data.get("title", "Follow")}
                    if data.get("image"):
                        layers["New picture layer"] = {"media": data.get("image")}

            pages.append({
                "template_uuid": template_uuid,
                "layers": layers
            })
            
        payload = {
            "pages": pages,
            "filename": filename
        }
        
        try:
            print(f">>> Sending request to Placid for {len(pages)} slides...")
            # DEBUG: Print payload (Keep debug for verification)
            print(f"DEBUG PAYLOAD: {json.dumps(payload, indent=2)}")
            
            response = requests.post(f"{self.base_url}/pdfs", headers=self.headers, json=payload)
            
            if response.status_code >= 400:
                print(f"API Error Status: {response.status_code}")
                print(f"API Error Response: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            print(f">>> Placid Response: {json.dumps(result)}")
            
            if result.get("pdf_url"):
                 return result.get("pdf_url")
            
            polling_url = result.get("polling_url")
            if polling_url:
                print(f">>> PDF queued. Polling {polling_url}...")
                for attempt in range(20): # 40s timeout
                    time.sleep(2)
                    poll_res = requests.get(polling_url, headers=self.headers)
                    if poll_res.status_code == 200:
                        poll_data = poll_res.json()
                        status = poll_data.get("status")
                        print(f">>> Polling status: {status}")
                        
                        if status == "finished":
                            return poll_data.get("pdf_url")
                        elif status == "failed":
                            print(f"Generation failed: {poll_data}")
                            return None
                    else:
                        print(f"Polling error: {poll_res.status_code}")
                
                print("Polling timed out.")
                return None
            
            return result.get("url") # Fallback
            
        except Exception as e:
            print(f"Error generating carousel: {e}")
            return None

if __name__ == "__main__":
    pass
