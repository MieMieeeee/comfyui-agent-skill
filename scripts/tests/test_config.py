"""Tests for comfyui.config module."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pathlib import Path

import pytest

from comfyui.config import check_server, COMFYUI_URL, SKILL_ROOT


class TestSkillRoot:
    def test_skill_root_is_directory(self):
        assert SKILL_ROOT.is_dir()

    def test_skill_root_contains_skill_md(self):
        assert (SKILL_ROOT / "SKILL.md").exists()

    def test_skill_root_contains_assets(self):
        assert (SKILL_ROOT / "assets").is_dir()

    def test_skill_root_contains_scripts(self):
        assert (SKILL_ROOT / "scripts").is_dir()


class TestCheckServer:
    def test_available_when_server_responds(self):
        """check_server returns available=True when ComfyUI /system_stats responds."""
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/system_stats":
                    body = json.dumps({"system": {"CPU": "info"}}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()
            def log_message(self, *args):
                pass  # suppress logs

        server = HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = Thread(target=server.handle_request, daemon=True)
        thread.start()

        url = f"http://127.0.0.1:{port}"
        result = check_server(url)

        assert result["available"] is True
        assert result["url"] == url
        assert "stats" in result

        server.server_close()

    def test_unavailable_when_server_down(self):
        """check_server returns available=False when no server is listening."""
        # Use a port that's almost certainly not listening
        result = check_server("http://127.0.0.1:59999")
        assert result["available"] is False
        assert result["url"] == "http://127.0.0.1:59999"
        assert "error" in result

    def test_default_url_from_env(self):
        """COMFYUI_URL defaults to 127.0.0.1:8188 or from env var."""
        # Just verify it's a non-empty string starting with http
        assert COMFYUI_URL.startswith("http")
