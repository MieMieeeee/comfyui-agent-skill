"""CLI entry point shim: delegates to `python -m comfyui`."""
import subprocess
import sys

if __name__ == "__main__":
    # Delegate to the module entry point
    sys.exit(subprocess.run([sys.executable, "-m", "comfyui", *sys.argv[1:]]).returncode)
