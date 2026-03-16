"""
Media Handler - Multiple methods to get images ready for Blotato publishing.

Options:
  1. Blotato Upload   - Upload local file to Blotato's servers (simplest)
  2. ImgBB Upload     - Free image hosting, returns public URL (no account needed)
  3. GitHub Raw URL   - If image is in a public repo
  4. Local File Path  - For review/preview only (not publishable)

Usage:
  url = upload_for_publishing("path/to/image.png", method="blotato")
  url = upload_for_publishing("path/to/image.png", method="imgbb")
"""

import os
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = PROJECT_ROOT / "media"
load_dotenv(PROJECT_ROOT / ".env")


def get_local_image(filename):
    """Get full path to an image in the media directory."""
    path = MEDIA_DIR / filename
    if path.exists():
        return path
    # Try without extension
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        candidate = MEDIA_DIR / f"{filename}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Image not found: {filename} in {MEDIA_DIR}")


def image_to_base64(image_path):
    """Convert a local image to base64 data URI."""
    path = Path(image_path)
    ext = path.suffix.lower().replace(".", "")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime};base64,{data}"


def upload_to_blotato(image_path):
    """
    Upload image to Blotato's servers via their media endpoint.
    Returns public URL hosted on database.blotato.com.

    This is the simplest method — Blotato handles hosting.
    """
    from . import api_client

    b64_data = image_to_base64(image_path)
    result = api_client.upload_media(b64_data)

    url = result.get("url", "")
    if url:
        print(f"  Uploaded to Blotato: {url}")
        return url
    raise RuntimeError(f"Blotato upload failed: {result}")


def upload_to_imgbb(image_path, api_key=None):
    """
    Upload image to ImgBB (free image hosting).
    Returns public URL. No account needed for basic use.

    Get a free API key at: https://api.imgbb.com/
    Or set IMGBB_API_KEY in .env
    """
    key = api_key or os.getenv("IMGBB_API_KEY", "")
    if not key:
        raise ValueError(
            "ImgBB API key not set. Get a free key at https://api.imgbb.com/\n"
            "Add IMGBB_API_KEY to your .env file"
        )

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    data = urllib.parse.urlencode({
        "key": key,
        "image": image_data,
    }).encode("utf-8")

    req = urllib.request.Request("https://api.imgbb.com/1/upload", data=data)

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    url = result.get("data", {}).get("url", "")
    if url:
        print(f"  Uploaded to ImgBB: {url}")
        return url
    raise RuntimeError(f"ImgBB upload failed: {result}")


def upload_for_publishing(image_path, method="blotato"):
    """
    Upload an image and return a public URL ready for Blotato publishing.

    Args:
        image_path: Path to local image file
        method: 'blotato' (recommended), 'imgbb', or 'url' (if already public)

    Returns:
        Public URL string
    """
    path = Path(image_path)
    if not path.exists():
        # Try media directory
        path = get_local_image(image_path)

    print(f"  Uploading {path.name} via {method}...")

    if method == "blotato":
        return upload_to_blotato(path)
    elif method == "imgbb":
        return upload_to_imgbb(path)
    elif method == "url":
        # Assume the path IS a URL already
        return str(image_path)
    else:
        raise ValueError(f"Unknown upload method: {method}. Use 'blotato', 'imgbb', or 'url'")


def list_available_images():
    """List all images in the media directory."""
    images = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        images.extend(MEDIA_DIR.glob(ext))
    return sorted(images, key=lambda p: p.stat().st_mtime, reverse=True)


def preview_image_info(image_path):
    """Get image dimensions and size for preview."""
    try:
        from PIL import Image
        img = Image.open(image_path)
        width, height = img.size
        size_kb = Path(image_path).stat().st_size / 1024
        return {
            "path": str(image_path),
            "filename": Path(image_path).name,
            "dimensions": f"{width}x{height}",
            "aspect_ratio": f"{width/height:.2f}",
            "size_kb": round(size_kb, 1),
            "is_square": abs(width - height) < 10,
            "format": img.format,
        }
    except ImportError:
        size_kb = Path(image_path).stat().st_size / 1024
        return {
            "path": str(image_path),
            "filename": Path(image_path).name,
            "size_kb": round(size_kb, 1),
        }


if __name__ == "__main__":
    print("Available images in media/:")
    for img in list_available_images()[:10]:
        info = preview_image_info(img)
        print(f"  {info['filename']:<40} {info.get('dimensions', '?'):<12} {info['size_kb']}KB")
