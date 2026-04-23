import json
import os
import urllib.error
import urllib.request
from pathlib import Path

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

# Resolve skill root from this file: config.py -> comfyui/ -> scripts/ -> skill_root/
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent


def check_server(url: str | None = None) -> dict:
    """Check ComfyUI availability via GET /system_stats.

    Returns dict with at least 'available' (bool) and 'url' (str).
    On success, includes 'stats' with the raw system_stats response.
    On failure, includes 'error' with the reason.
    """
    server_url = (url or COMFYUI_URL).rstrip("/")
    try:
        req = urllib.request.Request(f"{server_url}/system_stats")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {"available": True, "url": server_url, "stats": data}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return {"available": False, "url": server_url, "error": str(e)}
