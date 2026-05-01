"""Tests for comfyui.config module."""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pathlib import Path

import pytest

from comfyui.config import (
    check_server,
    get_comfyui_url,
    save_comfyui_url,
    SKILL_ROOT,
    DEFAULT_URL,
)


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
        assert "hint" in result
        assert "ComfyUI" in result["hint"] or "8188" in result["hint"] or "端口" in result["hint"]

    def test_unavailable_when_system_stats_not_json(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/system_stats":
                    body = b"not-json"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = Thread(target=server.handle_request, daemon=True)
        thread.start()

        url = f"http://127.0.0.1:{port}"
        result = check_server(url)

        assert result["available"] is False
        assert result["url"] == url
        assert "error" in result
        assert "hint" in result

        server.server_close()


class TestComfyuiUrlResolution:
    def test_default_when_no_env_and_no_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "nonexistent.json"
        monkeypatch.delenv("COMFYUI_URL", raising=False)
        monkeypatch.delenv("COMFYUI_CONFIG_FILE", raising=False)
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        url = get_comfyui_url()
        assert url == DEFAULT_URL

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("COMFYUI_URL", "http://192.168.1.100:8188")
        url = get_comfyui_url()
        assert url == "http://192.168.1.100:8188"

    def test_env_var_overrides_local_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        config_path.write_text(json.dumps({"comfyui_url": "http://from-config:8188"}))
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        monkeypatch.setenv("COMFYUI_URL", "http://from-env:8188")
        url = get_comfyui_url()
        assert url == "http://from-env:8188"

    def test_local_config_used_when_no_env(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        config_path.write_text(json.dumps({"comfyui_url": "http://192.168.1.50:8188"}))
        monkeypatch.delenv("COMFYUI_URL", raising=False)
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        url = get_comfyui_url()
        assert url == "http://192.168.1.50:8188"

    def test_falls_back_to_default_when_config_missing(self, tmp_path, monkeypatch):
        config_path = tmp_path / "nonexistent.json"
        monkeypatch.delenv("COMFYUI_URL", raising=False)
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        url = get_comfyui_url()
        assert url == DEFAULT_URL


class TestSaveComfyuiUrl:
    def test_saves_url_to_config_file(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        save_comfyui_url("http://192.168.1.100:8188")

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["comfyui_url"] == "http://192.168.1.100:8188"

    def test_preserves_existing_fields(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        config_path.write_text(json.dumps({"other_key": "keep_me"}))
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        save_comfyui_url("http://new-url:8188")

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["comfyui_url"] == "http://new-url:8188"
        assert data["other_key"] == "keep_me"

    def test_strips_trailing_slash(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        save_comfyui_url("http://192.168.1.100:8188/")

        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["comfyui_url"] == "http://192.168.1.100:8188"

    def test_rejects_empty_url(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        with pytest.raises(ValueError, match="empty"):
            save_comfyui_url("")

    def test_rejects_non_http_url(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.local.json"
        monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(config_path))
        with pytest.raises(ValueError, match="http"):
            save_comfyui_url("ftp://server:8188")
