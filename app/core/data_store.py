from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.providers.base import UsageData

_DB_DIR = Path(__file__).resolve().parent.parent.parent
_DB_PATH = _DB_DIR / "usage_history.db"


class DataStore:
    def __init__(self, db_path: Optional[Path] = None):
        self._path = db_path or _DB_PATH
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    # ── schema ──────────────────────────────────────────

    def _init_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                provider    TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                input_tokens  INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cached_tokens INTEGER DEFAULT 0,
                cost_usd    REAL    DEFAULT 0.0,
                model       TEXT    DEFAULT '',
                raw_json    TEXT    DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_provider_ts
            ON usage_records (provider, timestamp)
        """)
        self._conn.commit()

    # ── write ───────────────────────────────────────────

    def save_usage(self, provider: str, usage: UsageData, raw: Optional[dict] = None) -> None:
        self._conn.execute(
            """INSERT INTO usage_records
               (provider, timestamp, input_tokens, output_tokens, cached_tokens, cost_usd, model, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                provider,
                datetime.utcnow().isoformat(),
                usage.input_tokens,
                usage.output_tokens,
                usage.cached_tokens,
                usage.cost_usd,
                json.dumps(usage.model_breakdown, ensure_ascii=False),
                json.dumps(raw or {}, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    # ── read ────────────────────────────────────────────

    def query_usage(
        self,
        provider: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[dict]:
        sql = "SELECT * FROM usage_records WHERE provider = ?"
        params: list = [provider]

        if start:
            sql += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND timestamp <= ?"
            params.append(end.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_daily_summary(self, provider: str, days: int = 7) -> List[dict]:
        sql = """
            SELECT
                date(timestamp) as day,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cached_tokens) as total_cached,
                SUM(cost_usd) as total_cost,
                COUNT(*) as record_count
            FROM usage_records
            WHERE provider = ?
              AND timestamp >= datetime('now', ?)
            GROUP BY date(timestamp)
            ORDER BY day DESC
        """
        rows = self._conn.execute(sql, (provider, f"-{days} days")).fetchall()
        return [dict(r) for r in rows]

    # ── lifecycle ───────────────────────────────────────

    def close(self) -> None:
        self._conn.close()
