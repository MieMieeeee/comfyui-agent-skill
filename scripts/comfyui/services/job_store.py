"""SQLite-based job persistence for async polling."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class JobStore:
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id       TEXT PRIMARY KEY,
        workflow_id  TEXT NOT NULL,
        prompt       TEXT NOT NULL,
        text_inputs  TEXT,
        input_images TEXT,
        width        INTEGER,
        height       INTEGER,
        server_url   TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        status       TEXT NOT NULL,
        phase        TEXT,
        node         TEXT,
        outputs      TEXT,
        error        TEXT,
        seed         INTEGER,
        count        INTEGER,
        completed_at  TEXT,
        last_polled_at TEXT,
        last_error     TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
    """

    _FIELDS = (
        "job_id", "workflow_id", "prompt", "text_inputs", "input_images", "width", "height",
        "server_url", "created_at", "status", "phase", "node", "outputs",
        "error", "seed", "count", "completed_at", "last_polled_at", "last_error",
    )

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.executescript(self._SCHEMA)
        self._ensure_columns()
        self.db.row_factory = sqlite3.Row

    def _ensure_columns(self) -> None:
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(jobs)").fetchall()]
        migrations: list[tuple[str, str]] = [
            ("text_inputs", "TEXT"),
            ("last_polled_at", "TEXT"),
            ("last_error", "TEXT"),
        ]
        for name, sql_type in migrations:
            if name in cols:
                continue
            self.db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {sql_type}")
        self.db.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def save_job(self, **fields: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        fields.setdefault("created_at", now)
        fields.setdefault("status", "submitted")
        present = {k: fields[k] for k in self._FIELDS if k in fields}
        self.db.execute(
            "INSERT OR REPLACE INTO jobs ({}) VALUES ({})".format(
                ", ".join(present.keys()),
                ", ".join(["?"] * len(present)),
            ),
            tuple(present[k] for k in present),
        )
        self.db.commit()

    def save_batch(self, jobs: list[dict[str, Any]]) -> None:
        if not jobs:
            return
        now = datetime.now(timezone.utc).isoformat()
        cols_set: set[str] = set()
        for job in jobs:
            job.setdefault("created_at", now)
            job.setdefault("status", "submitted")
            cols_set.update(k for k in self._FIELDS if k in job)
        cols = [k for k in self._FIELDS if k in cols_set]
        rows = []
        for job in jobs:
            rows.append(tuple(job.get(c) for c in cols))
        self.db.executemany(
            "INSERT OR REPLACE INTO jobs ({}) VALUES ({})".format(
                ", ".join(cols), ", ".join(["?"] * len(cols)),
            ),
            rows,
        )
        self.db.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        cur = self.db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        setters = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(
            f"UPDATE jobs SET {setters} WHERE job_id = ?",
            tuple(fields[k] for k in fields) + (job_id,),
        )
        self.db.commit()

    def list_jobs(
        self,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if statuses is not None:
            placeholders = ",".join("?" * len(statuses))
            cur = self.db.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
                (*statuses, limit),
            )
        elif status:
            cur = self.db.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur = self.db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def delete_job(self, job_id: str) -> None:
        self.db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.commit()

    def delete_completed_old(self, days: int = 7) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cur = self.db.execute(
            "DELETE FROM jobs WHERE status = 'completed' AND created_at < ?",
            (cutoff,),
        )
        self.db.commit()
        return cur.rowcount
