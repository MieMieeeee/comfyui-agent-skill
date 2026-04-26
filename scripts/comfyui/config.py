import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8188"

# Resolve skill root from this file: config.py -> comfyui/ -> scripts/ -> skill_root/
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent

_LOCAL_CONFIG_PATH = SKILL_ROOT / "config.local.json"


def _load_local_config() -> dict:
    """Load config.local.json if it exists."""
    if _LOCAL_CONFIG_PATH.exists():
        try:
            return json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def get_comfyui_url() -> str:
    """Resolve ComfyUI server URL.

    Priority: env var COMFYUI_URL > config.local.json > default http://127.0.0.1:8188
    """
    env_url = os.environ.get("COMFYUI_URL")
    if env_url:
        return env_url
    local = _load_local_config()
    if "comfyui_url" in local:
        return local["comfyui_url"]
    return DEFAULT_URL


COMFYUI_URL = get_comfyui_url()


def save_comfyui_url(url: str) -> None:
    """Persist a ComfyUI server URL to config.local.json."""
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https://, got: {url}")
    config = _load_local_config()
    config["comfyui_url"] = url
    _LOCAL_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def check_server(url: str | None = None) -> dict:
    """Check ComfyUI availability via GET /system_stats.

    Returns dict with at least 'available' (bool) and 'url' (str).
    On success, includes 'stats' with the raw system_stats response.
    On failure, includes 'error' with the reason.
    """
    server_url = (url or get_comfyui_url()).rstrip("/")
    try:
        req = urllib.request.Request(f"{server_url}/system_stats")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {"available": True, "url": server_url, "stats": data}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return {"available": False, "url": server_url, "error": str(e)}
