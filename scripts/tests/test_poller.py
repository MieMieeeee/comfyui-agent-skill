"""Tests for the Poller (async job status polling layer)."""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comfyui.services.job_store import JobStore

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPollJobNotFound:
    def test_returns_error_when_job_not_in_store(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        result = poll_job("nonexistent", store, "http://127.0.0.1:8188")
        assert result["job_id"] == "nonexistent"
        assert result["status"] == "unknown"
        assert result["error"]["code"] == "JOB_NOT_FOUND"


class TestPollJobSubmitted:
    def test_returns_submitted_status(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-sub-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )
        # No history yet (HTTP fallback)
        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {}
            mock_cls.return_value = mock_inst

            result = poll_job("job-sub-1", store, "http://127.0.0.1:8188")

        assert result["job_id"] == "job-sub-1"
        assert result["status"] == "submitted"


class TestPollJobCompleted:
    def test_completed_marks_status_and_writes_outputs(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-done-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {
                "job-done-1": {
                    "outputs": {
                        "9": {
                            "images": [
                                {"filename": "img_00001.png", "subfolder": "", "type": "output"}
                            ]
                        }
                    }
                }
            }
            mock_inst.get_image.return_value = b"bytes"
            mock_cls.return_value = mock_inst

            result = poll_job(
                "job-done-1",
                store,
                "http://127.0.0.1:8188",
                skill_root=SKILL_ROOT,
                results_dir=tmp_path / "done_out",
            )

        assert result["status"] == "completed"
        assert "outputs" in result
        # Store should be updated
        row = store.get_job("job-done-1")
        assert row["status"] == "completed"
        assert row["outputs"] is not None

    def test_execution_error_marks_failed(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-err-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {
                "job-err-1": {
                    "status": {"errored": True},
                    "error": "OutOfMemory",
                }
            }
            mock_cls.return_value = mock_inst

            result = poll_job("job-err-1", store, "http://127.0.0.1:8188")

        assert result["status"] == "failed"
        assert isinstance(result["error"], dict)
        assert result["error"]["code"] == "COMFYUI_EXECUTION"


class TestPollJobExecuting:
    def test_executing_returns_current_status(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-exec-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="executing",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {}  # Not done yet
            mock_cls.return_value = mock_inst

            result = poll_job("job-exec-1", store, "http://127.0.0.1:8188")

        assert result["status"] == "executing"


class TestPollJobServerOverride:
    def test_server_url_override_for_poll(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-override",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://192.168.1.100:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {}
            mock_cls.return_value = mock_inst

            # Override server for this poll only
            result = poll_job("job-override", store, "http://127.0.0.1:8188")

        # Should have called with overridden URL
        mock_cls.assert_called_with("http://127.0.0.1:8188")
        assert result["status"] == "submitted"


class TestPollJobNoFalseFailure:
    def test_empty_history_does_not_mark_failed(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-empty",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {}  # No result
            mock_cls.return_value = mock_inst

            result = poll_job("job-empty", store, "http://127.0.0.1:8188")

        assert result["status"] in ("submitted", "executing")
        # error key may be None from store row, but no _err marker
        assert result.get("error") is None or "code" not in result.get("error", {})


class TestPollJobWebSocketProgress:
    def test_uses_websocket_for_progress(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-ws-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller._poll_ws_once", new_callable=AsyncMock) as mock_ws:
            mock_ws.return_value = {"phase": "executing", "node": "KSampler", "prompt_id": "job-ws-1"}

            with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
                mock_inst = MagicMock()
                mock_inst.get_history.return_value = {}  # Not completed
                mock_cls.return_value = mock_inst

                result = poll_job("job-ws-1", store, "http://127.0.0.1:8188")

            # WS returned progress info
            assert result["node"] == "KSampler"
            assert result["phase"] == "executing"


class TestPollJobStoreUpdate:
    def test_updates_store_with_phase_and_node(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-phase-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller._poll_ws_once", new_callable=AsyncMock) as mock_ws:
            mock_ws.return_value = {"phase": "executing", "node": "CLIPTextEncode", "prompt_id": "job-phase-1"}

            with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
                mock_inst = MagicMock()
                mock_inst.get_history.return_value = {}
                mock_cls.return_value = mock_inst

                poll_job("job-phase-1", store, "http://127.0.0.1:8188")

        row = store.get_job("job-phase-1")
        assert row["phase"] == "executing"
        assert row["node"] == "CLIPTextEncode"


class TestPollAllJobs:
    def test_poll_all_returns_only_pending_jobs(self, tmp_path):
        from comfyui.services.poller import poll_all_jobs
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-pending-1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )
        store.save_job(
            job_id="job-pending-2",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="executing",
        )
        store.save_job(
            job_id="job-done",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="completed",
        )

        with patch("comfyui.services.poller.poll_job") as mock_poll:
            mock_poll.side_effect = [
                {"job_id": "job-pending-1", "status": "executing"},
                {"job_id": "job-pending-2", "status": "executing"},
            ]

            results = poll_all_jobs(store, poll_server_url="http://127.0.0.1:8188")

        assert len(results) == 2
        assert mock_poll.call_count == 2

    def test_poll_all_uses_each_jobs_server_when_override_none(self, tmp_path):
        from comfyui.services.poller import poll_all_jobs
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="j1",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://192.168.1.10:8188",
            status="submitted",
        )
        store.save_job(
            job_id="j2",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://192.168.1.20:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller._sync_ws_poll", return_value=None):
            with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
                mock_inst = MagicMock()
                mock_inst.get_history.return_value = {}
                mock_cls.return_value = mock_inst
                poll_all_jobs(store, poll_server_url=None)

        urls = [call[0][0] for call in mock_cls.call_args_list]
        assert "http://192.168.1.10:8188" in urls
        assert "http://192.168.1.20:8188" in urls
        assert len(urls) >= 2

    def test_poll_all_empty_store(self, tmp_path):
        from comfyui.services.poller import poll_all_jobs
        store = JobStore(tmp_path / "jobs.db")
        results = poll_all_jobs(store, poll_server_url="http://127.0.0.1:8188")
        assert results == []


class TestPollJobOutputs:
    def test_completed_with_multiple_images(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-multi",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {
                "job-multi": {
                    "outputs": {
                        "9": {
                            "images": [
                                {"filename": "img_00001.png", "subfolder": "", "type": "output"},
                                {"filename": "img_00002.png", "subfolder": "", "type": "output"},
                            ]
                        }
                    }
                }
            }
            mock_inst.get_image.side_effect = [b"a", b"b"]
            mock_cls.return_value = mock_inst

            result = poll_job(
                "job-multi",
                store,
                "http://127.0.0.1:8188",
                skill_root=SKILL_ROOT,
                results_dir=tmp_path / "out",
            )

        assert result["status"] == "completed"
        assert isinstance(result["outputs"], list)
        assert len(result["outputs"]) == 2
        assert all("path" in o and "filename" in o and "size_bytes" in o for o in result["outputs"])

    def test_completed_sets_completed_at(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-time",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.get_history.return_value = {
                "job-time": {
                    "outputs": {
                        "9": {
                            "images": [{"filename": "img.png", "subfolder": "", "type": "output"}]
                        }
                    }
                }
            }
            mock_inst.get_image.return_value = b"x"
            mock_cls.return_value = mock_inst

            result = poll_job(
                "job-time",
                store,
                "http://127.0.0.1:8188",
                skill_root=SKILL_ROOT,
                results_dir=tmp_path / "out2",
            )

        assert result["status"] == "completed"
        assert "completed_at" in result or result["completed_at"] is not None
        row = store.get_job("job-time")
        assert row["completed_at"] is not None


class TestPollJobWsFinishedPhase:
    def test_ws_finished_without_history_uses_waiting_outputs_phase(self, tmp_path):
        from comfyui.services.poller import poll_job
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="job-fin",
            workflow_id="z_image_turbo",
            prompt="test",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )

        with patch("comfyui.services.poller._poll_ws_once", new_callable=AsyncMock) as mock_ws:
            mock_ws.return_value = {"phase": "finished", "prompt_id": "job-fin"}

            with patch("comfyui.services.poller.ComfyApiWrapper") as mock_cls:
                mock_inst = MagicMock()
                mock_inst.get_history.return_value = {}
                mock_cls.return_value = mock_inst

                result = poll_job("job-fin", store, "http://127.0.0.1:8188")

        assert result["status"] == "executing"
        assert result.get("phase") == "waiting_outputs"
