"""Tests for the Submitter (workflow submission layer)."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from comfyui.preflight import PreflightResult
from comfyui.services.job_store import JobStore

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _stub_preflight_for_submitter_unit_tests(monkeypatch):
    """Avoid HTTP preflight and server checks during mocked ComfyApiWrapper tests."""

    def _ok(url, path):
        return PreflightResult(ok=True, server_reachable=True)

    monkeypatch.setattr(
        "comfyui.services.submitter.preflight_registered_workflow",
        _ok,
    )
    monkeypatch.setattr(
        "comfyui.services.submitter.check_server",
        lambda url: {"available": True, "url": url},
    )


class TestSubmitWorkflowPreflight:
    """Preflight gate when not stubbed (override autouse)."""

    def test_preflight_failure_blocks_submit(self, tmp_path, monkeypatch):
        from comfyui.services import submitter as sm

        def bad_pf(url, path):
            return PreflightResult(
                ok=False,
                server_reachable=True,
                missing_node_types=["GhostLoader"],
                error="missing_node_types",
            )

        monkeypatch.setattr(sm, "preflight_registered_workflow", bad_pf)

        result = sm.submit_workflow(
            workflow_id="z_image_turbo",
            prompt="hi",
            skill_root=SKILL_ROOT,
            job_store_path=tmp_path / "jobs.db",
            server_url="http://127.0.0.1:8188",
            skip_preflight=False,
        )
        assert result["submitted"] is False
        assert result["error"]["code"] == "PREFLIGHT_MISSING_NODES"
        assert "GhostLoader" in result["preflight"]["missing_node_types"]


class TestSubmitWorkflowValidation:
    def test_missing_workflow_returns_error(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        result = submit_workflow(
            workflow_id="nonexistent",
            prompt="test",
            skill_root=tmp_path,
        )
        assert result["submitted"] is False
        assert result["error"]["code"] == "WORKFLOW_NOT_REGISTERED"

    def test_empty_prompt_returns_error(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        result = submit_workflow(
            workflow_id="z_image_turbo",
            prompt="",
            skill_root=tmp_path,
        )
        assert result["submitted"] is False
        assert result["error"]["code"] == "EMPTY_PROMPT"

    def test_whitespace_only_prompt_returns_error(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        result = submit_workflow(
            workflow_id="z_image_turbo",
            prompt="   ",
            skill_root=tmp_path,
        )
        assert result["submitted"] is False
        assert result["error"]["code"] == "EMPTY_PROMPT"


class TestSubmitWorkflowSave:
    def test_saves_job_to_store(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "real-job-1"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="a cute cat",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                server_url="http://127.0.0.1:8188",
            )
        assert result["submitted"] is True
        assert len(result["job_ids"]) == 1
        job_id = result["job_ids"][0]

        store = JobStore(store_path)
        row = store.get_job(job_id)
        assert row is not None
        assert row["workflow_id"] == "z_image_turbo"
        assert row["prompt"] == "a cute cat"
        assert row["status"] == "submitted"
        assert row["server_url"] == "http://127.0.0.1:8188"

    def test_returns_job_id_from_queue_prompt(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "abc123"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="test prompt",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is True
        assert result["job_ids"] == ["abc123"]
        mock_api.queue_prompt.assert_called_once()

    def test_count_greater_than_one_saves_multiple_jobs(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.side_effect = [
            {"prompt_id": f"id-{i}"} for i in range(3)
        ]

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="a cute cat",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                count=3,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is True
        assert len(result["job_ids"]) == 3
        assert result["job_ids"] == ["id-0", "id-1", "id-2"]

        store = JobStore(store_path)
        rows = store.list_jobs()
        assert len(rows) == 3
        assert all(r["workflow_id"] == "z_image_turbo" for r in rows)
        assert all(r["status"] == "submitted" for r in rows)

    def test_count_one_saves_single_job(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "single-id"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="single",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                count=1,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is True
        assert len(result["job_ids"]) == 1
        store = JobStore(store_path)
        assert len(store.list_jobs()) == 1


class TestSubmitWorkflowInputImages:
    def test_uploads_image_and_sets_node_param(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"

        img_file = SKILL_ROOT / "assets" / "workflows" / "test_input.png"
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"fake png")

        try:
            mock_api = MagicMock()
            mock_api.queue_prompt.return_value = {"prompt_id": "img-job-1"}
            mock_api.upload_image.return_value = {
                "name": "test_input.png",
                "subfolder": "default_upload_folder",
                "type": "input",
            }

            with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
                result = submit_workflow(
                    workflow_id="klein_edit",
                    prompt="edit this",
                    skill_root=SKILL_ROOT,
                    job_store_path=store_path,
                    input_images={"input_image": img_file},
                    server_url="http://127.0.0.1:8188",
                )

            assert result["submitted"] is True
            mock_api.upload_image.assert_called_once()
        finally:
            img_file.unlink(missing_ok=True)

    def test_missing_required_image_returns_error(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"

        with patch("comfyui.services.submitter.ComfyApiWrapper"):
            result = submit_workflow(
                workflow_id="klein_edit",
                prompt="edit this",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                input_images={"input_image": tmp_path / "nonexistent.png"},
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is False
        assert result["error"]["code"] == "INPUT_IMAGE_NOT_FOUND"


class TestSubmitWorkflowSeed:
    def test_generates_seed_when_not_provided(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "seed-test"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="test",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is True
        store = JobStore(store_path)
        row = store.get_job(result["job_ids"][0])
        assert row["seed"] is not None

    def test_uses_provided_seed(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "seed-provided"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="test",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                seed=12345,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is True
        store = JobStore(store_path)
        row = store.get_job(result["job_ids"][0])
        assert row["seed"] == 12345


class TestSubmitWorkflowDimensions:
    def test_uses_provided_width_height(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "dims-test"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="test",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                width=1024,
                height=768,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is True
        store = JobStore(store_path)
        row = store.get_job(result["job_ids"][0])
        assert row["width"] == 1024
        assert row["height"] == 768

    def test_workflow_managed_size_not_stored(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"

        img_file = SKILL_ROOT / "assets" / "workflows" / "test_input.png"
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"fake png")

        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "managed-size"}
        mock_api.upload_image.return_value = {
            "name": "test_input.png",
            "subfolder": "default_upload_folder",
            "type": "input",
        }

        try:
            with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
                result = submit_workflow(
                    workflow_id="klein_edit",
                    prompt="test",
                    skill_root=SKILL_ROOT,
                    job_store_path=store_path,
                    input_images={"input_image": img_file},
                    width=512,
                    height=512,
                    server_url="http://127.0.0.1:8188",
                )

            assert result["submitted"] is True
            store = JobStore(store_path)
            row = store.get_job(result["job_ids"][0])
            assert row["width"] is None
            assert row["height"] is None
        finally:
            img_file.unlink(missing_ok=True)

    def test_ltx_t2v_stores_provided_dimensions(self, tmp_path):
        from comfyui.services.submitter import submit_workflow

        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "ltx-t2v-dims"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="ltx_23_t2v_distill",
                prompt="pan shot",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                width=1920,
                height=1088,
                server_url="http://127.0.0.1:8188",
                skip_preflight=True,
            )

        assert result["submitted"] is True
        store = JobStore(store_path)
        row = store.get_job("ltx-t2v-dims")
        assert row["width"] == 1920
        assert row["height"] == 1088

    def test_ltx_t2v_stores_config_defaults_when_dimensions_omitted(self, tmp_path):
        from comfyui.services.submitter import submit_workflow

        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "ltx-t2v-default"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="ltx_23_t2v_distill",
                prompt="motion",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                server_url="http://127.0.0.1:8188",
                skip_preflight=True,
            )

        assert result["submitted"] is True
        row = JobStore(store_path).get_job("ltx-t2v-default")
        assert row["width"] == 768
        assert row["height"] == 512

    def test_ltx_i2v_stores_dimensions_with_input_image(self, tmp_path):
        from comfyui.services.submitter import submit_workflow

        img_file = SKILL_ROOT / "assets" / "workflows" / "test_input_i2v.png"
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"fake png")

        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "ltx-i2v-dims"}
        mock_api.upload_image.return_value = {
            "name": "test_input_i2v.png",
            "subfolder": "default_upload_folder",
            "type": "input",
        }

        try:
            with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
                result = submit_workflow(
                    workflow_id="ltx_23_i2v_distilled",
                    prompt="animate",
                    skill_root=SKILL_ROOT,
                    job_store_path=store_path,
                    input_images={"input_image": img_file},
                    width=1920,
                    height=1088,
                    server_url="http://127.0.0.1:8188",
                    skip_preflight=True,
                )

            assert result["submitted"] is True
            row = JobStore(store_path).get_job("ltx-i2v-dims")
            assert row["width"] is None
            assert row["height"] is None
        finally:
            img_file.unlink(missing_ok=True)


class TestSubmitWorkflowServerUnavailable:
    def test_server_unavailable_returns_error(self, tmp_path):
        from comfyui.services.submitter import submit_workflow
        store_path = tmp_path / "jobs.db"

        with patch("comfyui.services.submitter.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.queue_prompt.side_effect = Exception("Connection refused")
            mock_cls.return_value = mock_inst

            result = submit_workflow(
                workflow_id="z_image_turbo",
                prompt="test",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                server_url="http://127.0.0.1:8188",
            )

        assert result["submitted"] is False
        assert "error" in result


class TestSubmitQwen3TTS:
    def test_stores_json_prompt_for_audio_workflow(self, tmp_path):
        from comfyui.services.submitter import submit_workflow

        store_path = tmp_path / "jobs.db"
        mock_api = MagicMock()
        mock_api.queue_prompt.return_value = {"prompt_id": "tts-job-1"}

        with patch("comfyui.services.submitter.ComfyApiWrapper", return_value=mock_api):
            result = submit_workflow(
                workflow_id="qwen3_tts",
                prompt="",
                skill_root=SKILL_ROOT,
                job_store_path=store_path,
                server_url="http://127.0.0.1:8188",
                text_inputs={"speech_text": "你好", "instruct": "女声"},
            )

        assert result["submitted"] is True
        row = JobStore(store_path).get_job("tts-job-1")
        parsed = json.loads(row["prompt"])
        assert parsed["speech_text"] == "你好"
        assert parsed["instruct"] == "女声"
