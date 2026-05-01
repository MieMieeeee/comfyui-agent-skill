"""Command-line entry: generation, health check, and workflow import."""
from __future__ import annotations

import json
import sys

from comfyui.cli_admin import cmd_check, cmd_import_workflow, cmd_save_server
from comfyui.cli_generate import cmd_generate


def main_module() -> None:
    """`python -m comfyui` subcommands: check | save-server | import-workflow | generate"""
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(
            "Usage:\n"
            "  python -m comfyui check\n"
            "  python -m comfyui save-server URL\n"
            "  python -m comfyui import-workflow PATH\n"
            "  python -m comfyui generate [options]\n"
            "\n"
            "Examples:\n"
            "  python -m comfyui generate -p \"a cat\" --output ./out\n"
            "  python -m comfyui generate -p \"happy cat\" -p \"sad cat\" -p \"surprised cat\" --output ./expressions\n"
            "  python -m comfyui generate --workflow klein_edit --image input_image=photo.png -p \"change outfit\"",
            file=sys.stderr,
        )
        sys.exit(0)

    # No args: fall through to generate (will report missing prompt via EMPTY_PROMPT)
    if len(sys.argv) < 2:
        sys.exit(cmd_generate())

    sub = sys.argv[1]

    # Route subcommands FIRST (before any flag checks)
    if sub in ("check", "save-server", "generate", "import-workflow"):
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        if sub == "check":
            sys.exit(cmd_check())
        if sub == "save-server":
            sys.exit(cmd_save_server())
        if sub == "import-workflow":
            sys.exit(cmd_import_workflow())
        sys.exit(cmd_generate())

    # Handle --check flag (not a subcommand)
    if "--check" in sys.argv[1:]:
        # Strip --check and delegate to cmd_check
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[2:] if a != "--check"]
        sys.exit(cmd_check())

    # Handle --save-server flag (not a subcommand)
    if "--save-server" in sys.argv[1:]:
        idx = sys.argv.index("--save-server")
        url_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--") else None
        # Build new argv: [prog, url, ...remaining args except --save-server and its value]
        remaining = [a for i, a in enumerate(sys.argv) if i not in (idx, idx + 1)]
        sys.argv = [sys.argv[0], url_arg] + remaining[1:]
        sys.exit(cmd_save_server())

    # Legacy mode: if the first token looks like a flag, treat it as generate.
    if sub.startswith("-"):
        sys.exit(cmd_generate())

    print(f"Unknown subcommand: {sub}. Use: check | save-server | import-workflow | generate", file=sys.stderr)
    sys.exit(2)
