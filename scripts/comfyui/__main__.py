"""`python -m comfyui` → 子命令入口 (check / save-server / generate)."""
import json
import os
import sys

# Warn if not running via `uv run`
if not os.environ.get("UV") and os.path.exists(".venv"):
    sub = sys.argv[1] if len(sys.argv) > 1 else ""
    print(
        f"Hint: Use 'uv run --no-sync python -m comfyui {sub}' instead of bare 'python -m comfyui {sub}'.",
        "This ensures the correct virtual environment is used.",
        file=sys.stderr,
    )

try:
    from comfyui.cli import main_module
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": {
            "code": "DEPENDENCY_UNAVAILABLE",
            "message": f"Missing dependency: {e}. Run 'uv sync' from the skill root directory.",
        },
    }))
    sys.exit(1)

if __name__ == "__main__":
    main_module()
