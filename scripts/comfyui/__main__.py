"""`python -m comfyui` → 子命令入口 (check / save-server / generate)."""
import os
import sys

# Warn if not running via `uv run`
if not os.environ.get("UV") and os.path.exists(".venv"):
    sub = sys.argv[1] if len(sys.argv) > 1 else ""
    print(
        f"Hint: Use 'uv run python -m comfyui {sub}' instead of bare 'python -m comfyui {sub}'.",
        "This ensures the correct virtual environment is used.",
        file=sys.stderr,
    )

from comfyui.cli import main_module

if __name__ == "__main__":
    main_module()
