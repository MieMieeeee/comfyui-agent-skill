"""Tests for the JobStore (SQLite job persistence layer)."""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from comfyui.services.job_store import JobStore


class TestJobStoreInit:
    def test_creates_db_file(self, tmp_path):
        db = tmp_path / "jobs.db"
        store = JobStore(db)
        assert db.exists()

    def test_creates_schema(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        rows = store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        ).fetchall()
        assert len(rows) == 1

    def test_creates_status_and_created_at_indexes(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        indexes = store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='jobs'"
        ).fetchall()
        index_names = [r[0] for r in indexes]
        assert "idx_jobs_status" in index_names
        assert "idx_jobs_created_at" in index_names

    def test_schema_has_text_inputs_column(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        cols = [r[1] for r in store.db.execute("PRAGMA table_info(jobs)").fetchall()]
        assert "text_inputs" in cols


class TestJobStoreSave:
    def test_save_job_stores_all_fields(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="j1",
            workflow_id="z_image_turbo",
            prompt="a cute cat",
            server_url="http://127.0.0.1:8188",
            status="submitted",
            input_images=json.dumps({"input_image": "/path/to/cat.png"}),
            width=832,
            height=1280,
            seed=42,
            count=1,
        )
        row = store.get_job("j1")
        assert row is not None
        assert row["job_id"] == "j1"
        assert row["workflow_id"] == "z_image_turbo"
        assert row["prompt"] == "a cute cat"
        assert row["server_url"] == "http://127.0.0.1:8188"
        assert row["status"] == "submitted"
        assert json.loads(row["input_images"]) == {"input_image": "/path/to/cat.png"}
        assert row["width"] == 832
        assert row["height"] == 1280
        assert row["seed"] == 42
        assert row["count"] == 1

    def test_save_job_no_optional_fields(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(
            job_id="j1",
            workflow_id="z_image_turbo",
            prompt="a cute cat",
            server_url="http://127.0.0.1:8188",
            status="submitted",
        )
        row = store.get_job("j1")
        assert row["input_images"] is None
        assert row["width"] is None
        assert row["height"] is None
        assert row["seed"] is None
        assert row["count"] is None

    def test_save_batch_multiple_jobs(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        created_at = datetime.now(timezone.utc).isoformat()
        jobs = [
            {
                "job_id": f"job-{i}",
                "workflow_id": "klein_edit",
                "prompt": f"edit {i}",
                "server_url": "http://127.0.0.1:8188",
                "status": "submitted",
                "count": 3,
                "created_at": created_at,
            }
            for i in range(3)
        ]
        store.save_batch(jobs)
        rows = store.list_jobs()
        assert len(rows) == 3
        assert all(r["workflow_id"] == "klein_edit" for r in rows)

    def test_save_batch_heterogeneous_optional_fields(self, tmp_path):
        """Rows with different optional keys must align to same columns (NULL fill)."""
        store = JobStore(tmp_path / "jobs.db")
        jobs = [
            {
                "job_id": "a",
                "workflow_id": "z_image_turbo",
                "prompt": "p1",
                "server_url": "http://127.0.0.1:8188",
                "status": "submitted",
                "seed": 111,
            },
            {
                "job_id": "b",
                "workflow_id": "z_image_turbo",
                "prompt": "p2",
                "server_url": "http://127.0.0.1:8188",
                "status": "submitted",
                "width": 512,
            },
        ]
        store.save_batch(jobs)
        ra = store.get_job("a")
        rb = store.get_job("b")
        assert ra["seed"] == 111
        assert ra["width"] is None
        assert rb["width"] == 512
        assert rb["seed"] is None

    def test_save_duplicate_job_id_replaces(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p1",
                        server_url="http://127.0.0.1:8188", status="submitted")
        store.save_job(job_id="j1", workflow_id="z", prompt="p2",
                        server_url="http://127.0.0.1:8188", status="executing")
        row = store.get_job("j1")
        assert row["prompt"] == "p2"
        assert row["status"] == "executing"


class TestJobStoreGet:
    def test_get_job_not_found(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        assert store.get_job("nonexistent") is None

    def test_get_job_returns_dict(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="submitted")
        row = store.get_job("j1")
        assert isinstance(row, dict)
        assert row["job_id"] == "j1"


class TestJobStoreUpdate:
    def test_update_job_sets_fields(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="submitted")
        store.update_job("j1", status="executing", node="KSampler", phase="executing")
        row = store.get_job("j1")
        assert row["status"] == "executing"
        assert row["node"] == "KSampler"
        assert row["phase"] == "executing"

    def test_update_job_completed_with_outputs(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="submitted")
        outputs = json.dumps([{"path": "/results/img.png", "filename": "img.png", "size_bytes": 12345}])
        store.update_job("j1", status="completed", outputs=outputs,
                         completed_at="2026-04-28T12:00:00Z")
        row = store.get_job("j1")
        assert row["status"] == "completed"
        assert json.loads(row["outputs"]) == [{"path": "/results/img.png", "filename": "img.png", "size_bytes": 12345}]

    def test_update_job_failed_with_error(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="submitted")
        store.update_job("j1", status="failed", error="ComfyUI out of memory")
        row = store.get_job("j1")
        assert row["status"] == "failed"
        assert row["error"] == "ComfyUI out of memory"

    def test_update_job_not_found_noop(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.update_job("nonexistent", status="executing")  # no raise
        assert store.get_job("nonexistent") is None


class TestJobStoreList:
    def test_list_jobs_default_all(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        for i in range(5):
            store.save_job(job_id=f"j{i}", workflow_id="z", prompt=f"p{i}",
                           server_url="http://127.0.0.1:8188", status="submitted")
        rows = store.list_jobs()
        assert len(rows) == 5

    def test_list_jobs_filter_by_status(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p1",
                       server_url="http://127.0.0.1:8188", status="submitted")
        store.save_job(job_id="j2", workflow_id="z", prompt="p2",
                       server_url="http://127.0.0.1:8188", status="completed")
        rows = store.list_jobs(status="completed")
        assert len(rows) == 1
        assert rows[0]["job_id"] == "j2"

    def test_list_jobs_respects_limit(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        for i in range(5):
            store.save_job(job_id=f"j{i}", workflow_id="z", prompt=f"p{i}",
                           server_url="http://127.0.0.1:8188", status="submitted")
        rows = store.list_jobs(limit=3)
        assert len(rows) == 3

    def test_list_jobs_multiple_statuses(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="s1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="submitted")
        store.save_job(job_id="e1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="executing")
        store.save_job(job_id="c1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="completed")
        rows = store.list_jobs(statuses=("submitted", "executing"))
        ids = {r["job_id"] for r in rows}
        assert ids == {"s1", "e1"}


class TestJobStoreDelete:
    def test_delete_job_removes_record(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.save_job(job_id="j1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="submitted")
        store.delete_job("j1")
        assert store.get_job("j1") is None

    def test_delete_job_not_found_noop(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        store.delete_job("nonexistent")  # no raise


class TestJobStoreCleanup:
    def test_delete_completed_old_only_deletes_old_completed(self, tmp_path):
        store = JobStore(tmp_path / "jobs.db")
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        new_date = datetime.now(timezone.utc).isoformat()
        store.save_job(job_id="j1", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="completed",
                       created_at=old_date)
        store.save_job(job_id="j2", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="completed",
                       created_at=new_date)
        store.save_job(job_id="j3", workflow_id="z", prompt="p",
                       server_url="http://127.0.0.1:8188", status="executing",
                       created_at=old_date)
        deleted = store.delete_completed_old(days=7)
        assert deleted == 1
        assert store.get_job("j1") is None
        assert store.get_job("j2") is not None
        assert store.get_job("j3") is not None
