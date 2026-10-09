"""Ensure vendored comfy_api_simplified is used (no missing git+ install)."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from comfy_api_simplified import ComfyApiWrapper


def test_vendored_package_lives_under_scripts() -> None:
    import comfy_api_simplified

    root = Path(comfy_api_simplified.__file__).resolve().parent
    assert root.name == "comfy_api_simplified"
    assert (root / "api.py").is_file()
    assert (root / "workflow.py").is_file()
    assert (root / "exceptions.py").is_file()
    assert (root / "LICENSE").is_file()


def test_comfy_api_wrapper_instantiates() -> None:
    api = ComfyApiWrapper("http://127.0.0.1:8188")
    assert "8188" in api.url


def _ok_response(payload: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.reason = "OK"
    resp.content = b"bytes"
    resp.text = "ok"
    resp.json.return_value = payload if payload is not None else {}
    return resp


# --- HTTP timeouts -----------------------------------------------------------
# Every requests call must carry an explicit timeout; an unbounded call hangs
# forever when the server stops responding.


def test_default_timeouts_are_bounded() -> None:
    api = ComfyApiWrapper("http://127.0.0.1:8188")
    assert api.timeout == (10.0, 60.0)


def test_timeouts_are_configurable() -> None:
    api = ComfyApiWrapper("http://127.0.0.1:8188", connect_timeout=3.0, read_timeout=7.5)
    assert api.timeout == (3.0, 7.5)


@patch("comfy_api_simplified.api.requests.post")
def test_queue_prompt_sends_timeout(mock_post) -> None:
    mock_post.return_value = _ok_response({"prompt_id": "abc"})
    api = ComfyApiWrapper("http://127.0.0.1:8188", connect_timeout=3.0, read_timeout=7.5)

    assert api.queue_prompt({"1": {}}) == {"prompt_id": "abc"}
    assert mock_post.call_args.kwargs["timeout"] == (3.0, 7.5)


@patch("comfy_api_simplified.api.requests.get")
def test_read_calls_send_timeout(mock_get) -> None:
    mock_get.return_value = _ok_response({"p": 1})
    api = ComfyApiWrapper("http://127.0.0.1:8188", connect_timeout=3.0, read_timeout=7.5)

    api.get_history("abc")
    api.get_queue()
    api.get_image("a.png", "", "output")
    api.get_video("a.mp4", "", "output")

    assert mock_get.call_count == 4
    for call in mock_get.call_args_list:
        assert call.kwargs["timeout"] == (3.0, 7.5)


@patch("comfy_api_simplified.api.requests.post")
def test_uploads_send_timeout(mock_post, tmp_path) -> None:
    mock_post.return_value = _ok_response({"name": "a.png", "subfolder": ""})
    media = tmp_path / "a.bin"
    media.write_bytes(b"data")
    api = ComfyApiWrapper("http://127.0.0.1:8188", connect_timeout=3.0, read_timeout=7.5)

    api.upload_image(str(media))
    api.upload_media(str(media))

    assert mock_post.call_count == 2
    for call in mock_post.call_args_list:
        assert call.kwargs["timeout"] == (3.0, 7.5)


@patch("comfy_api_simplified.api.requests.post")
def test_timeout_exception_propagates(mock_post) -> None:
    import requests

    mock_post.side_effect = requests.exceptions.ReadTimeout("read timed out")
    api = ComfyApiWrapper("http://127.0.0.1:8188")

    with pytest.raises(requests.exceptions.ReadTimeout):
        api.queue_prompt({"1": {}})


# --- Config resolution -------------------------------------------------------


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point config.local.json at a temp file and clear timeout env vars."""
    cfg = tmp_path / "config.local.json"
    monkeypatch.setenv("COMFYUI_CONFIG_FILE", str(cfg))
    monkeypatch.delenv("COMFYUI_HTTP_CONNECT_TIMEOUT", raising=False)
    monkeypatch.delenv("COMFYUI_HTTP_READ_TIMEOUT", raising=False)
    return cfg


def test_timeout_defaults_when_unset(isolated_config) -> None:
    from comfyui.config import get_http_timeout

    assert get_http_timeout() == (10.0, 60.0)


def test_timeout_from_config_file(isolated_config) -> None:
    from comfyui.config import get_http_timeout

    isolated_config.write_text(
        json.dumps({"http_connect_timeout": 2, "http_read_timeout": 15}),
        encoding="utf-8",
    )
    assert get_http_timeout() == (2.0, 15.0)


def test_env_overrides_config_file(isolated_config, monkeypatch) -> None:
    from comfyui.config import get_http_timeout

    isolated_config.write_text(json.dumps({"http_read_timeout": 15}), encoding="utf-8")
    monkeypatch.setenv("COMFYUI_HTTP_READ_TIMEOUT", "99")
    assert get_http_timeout() == (10.0, 99.0)


@pytest.mark.parametrize("bad", ["abc", "-1", "0", "", None, []])
def test_invalid_timeout_falls_back_to_default(isolated_config, monkeypatch, bad) -> None:
    from comfyui.config import get_http_timeout

    if bad is None:
        monkeypatch.delenv("COMFYUI_HTTP_READ_TIMEOUT", raising=False)
        isolated_config.write_text(json.dumps({"http_read_timeout": [1]}), encoding="utf-8")
    else:
        monkeypatch.setenv("COMFYUI_HTTP_READ_TIMEOUT", str(bad))
    assert get_http_timeout()[1] == 60.0


def test_corrupt_config_falls_back_to_default(isolated_config) -> None:
    from comfyui.config import get_http_timeout

    isolated_config.write_text("{not json", encoding="utf-8")
    assert get_http_timeout() == (10.0, 60.0)


def test_save_comfyui_url_preserves_timeout_keys(isolated_config) -> None:
    from comfyui.config import get_http_timeout, save_comfyui_url

    isolated_config.write_text(json.dumps({"http_read_timeout": 25}), encoding="utf-8")
    save_comfyui_url("http://127.0.0.1:8189")

    assert get_http_timeout() == (10.0, 25.0)
    assert json.loads(isolated_config.read_text(encoding="utf-8"))["comfyui_url"].endswith("8189")