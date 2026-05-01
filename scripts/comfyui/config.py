import json
import os
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8188"

# Resolve skill root from this file: config.py -> comfyui/ -> scripts/ -> skill_root/
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent


def job_store_path() -> Path:
    """Path to the SQLite job store. Override with env ``COMFYUI_JOB_STORE``."""
    override = os.environ.get("COMFYUI_JOB_STORE")
    if override:
        return Path(override).expanduser().resolve()
    return SKILL_ROOT / "jobs.db"


def local_config_path() -> Path:
    """Path to the local JSON file for comfyui_url and other keys.

    Override with env ``COMFYUI_CONFIG_FILE`` (absolute or relative path) for tests
    or non-default layouts. Default: ``<skill root>/config.local.json``.
    """
    override = os.environ.get("COMFYUI_CONFIG_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return SKILL_ROOT / "config.local.json"


def _load_local_config() -> dict:
    """Load config.local.json if it exists."""
    path = local_config_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
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


def save_comfyui_url(url: str) -> None:
    """Persist a ComfyUI server URL to config.local.json."""
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")
    url = url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must start with http:// or https://, got: {url}")
    if not parsed.netloc:
        raise ValueError(f"URL must include host (and optional port), got: {url}")
    config = _load_local_config()
    config["comfyui_url"] = url
    path = local_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


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
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError, json.JSONDecodeError) as e:
        err = str(e)
        hint = (
            f"Hint / 提示: Make sure ComfyUI is running and the IP/port is correct (current: {server_url}). "
            f"请确认 ComfyUI 已启动，且可访问 {server_url}（检查 IP/端口、防火墙与是否在同一台机器上）。"
        )
        return {"available": False, "url": server_url, "error": err, "hint": hint}
