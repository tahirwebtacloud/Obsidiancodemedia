import json
import os
import time
import uuid

PRICING = {
    # Text Generation
    "gemini_input": 0.00010,
    "gemini_output": 0.00040,
    # Image Generation
    "imagen_per_image": 0.040,
    # Apify Tasks
    "apify_per_page": 0.005,
    "apify_per_yt_video": 0.008,
}

def calculate_gemini_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000.0) * PRICING["gemini_input"] + (output_tokens / 1000.0) * PRICING["gemini_output"]

class CostTracker:
    def __init__(self, run_id: str = "default"):
        self.costs = []
        self.start_time = time.time()
        self.run_id = run_id
        self.filename = f".tmp/run_costs_{self.run_id}.json"
        self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.costs = data.get("costs", [])
                    self.start_time = data.get("start_time", self.start_time)
            except Exception:
                pass

    def _update_cost(self, new_item):
        try:
            from execution.file_locker import FileLock
        except ImportError:
            try:
                from file_locker import FileLock
            except ImportError:
                FileLock = None
                
        os.makedirs(".tmp", exist_ok=True)
        if FileLock:
            try:
                with FileLock(self.filename):
                    self._load()
                    self.costs.append(new_item)
                    self._save_raw()
            except Exception as e:
                print(f"[CostTracker] Lock error: {e}")
                self.costs.append(new_item)
                self._save_raw()
        else:
            self._load()
            self.costs.append(new_item)
            self._save_raw()

    def _save_raw(self):
        data = {
            "costs": self.costs,
            "start_time": self.start_time,
            "total_cost": self.get_total_cost(),
            "duration_ms": self.get_duration_ms()
        }
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _save(self):
        # Kept for backward compatibility if called manually
        if hasattr(self, '_save_raw'):
            self._save_raw()

    def add_gemini_cost(self, operation: str, input_tokens: int, output_tokens: int, model: str = "Gemini"):
        cost = calculate_gemini_cost(input_tokens, output_tokens)
        self._update_cost({
            "service": model,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        })
        
    def add_image_cost(self, operation: str = "Generate Image", model: str = "Imagen 3"):
        self._update_cost({
            "service": model,
            "operation": operation,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": PRICING["imagen_per_image"]
        })
        
    def add_apify_page_cost(self, pages: int = 1, operation: str = "Web Scrape"):
        self._update_cost({
            "service": "Apify",
            "operation": operation,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": PRICING["apify_per_page"] * pages
        })

    def add_apify_yt_video_cost(self, videos: int = 1, operation: str = "YouTube Scrape"):
        self._update_cost({
            "service": "Apify",
            "operation": operation,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": PRICING["apify_per_yt_video"] * videos
        })

    def get_total_cost(self) -> float:
        return sum(item["cost"] for item in self.costs)
        
    def get_duration_ms(self) -> int:
        return int((time.time() - self.start_time) * 1000)

    def to_dict(self):
        return {
            "costs": self.costs,
            "total_cost": self.get_total_cost(),
            "duration_ms": self.get_duration_ms()
        }
