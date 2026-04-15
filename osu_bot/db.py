from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrackerRow:
    guild_id: int
    channel_id: int
    user_id: int
    username: str
    ruleset: str


@dataclass
class TrackerState:
    snapshot: dict[str, Any] | None
    recent_score_ids: list[str]
    account_issue: str | None
    last_play_time: float | None
    pending_snapshot: dict[str, Any] | None
    pending_changes: list[dict[str, Any]] | None


class TrackerDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS trackers (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                ruleset TEXT NOT NULL DEFAULT 'osu',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS tracker_state (
                channel_id INTEGER PRIMARY KEY,
                snapshot_json TEXT,
                recent_score_ids_json TEXT,
                account_issue TEXT,
                last_play_time REAL,
                pending_snapshot_json TEXT,
                pending_changes_json TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(channel_id) REFERENCES trackers(channel_id) ON DELETE CASCADE
            );
            """
        )
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(tracker_state)").fetchall()}
        for col, definition in [
            ("last_play_time",       "REAL"),
            ("pending_snapshot_json","TEXT"),
            ("pending_changes_json", "TEXT"),
        ]:
            if col not in cols:
                self.conn.execute(f"ALTER TABLE tracker_state ADD COLUMN {col} {definition}")

    def upsert_tracker(
        self, guild_id: int, channel_id: int, user_id: int, username: str, ruleset: str
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO trackers(channel_id, guild_id, user_id, username, ruleset)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                guild_id=excluded.guild_id,
                user_id=excluded.user_id,
                username=excluded.username,
                ruleset=excluded.ruleset
            """,
            (channel_id, guild_id, user_id, username, ruleset),
        )
        self.conn.commit()

    def remove_tracker(self, channel_id: int) -> int:
        cur = self.conn.execute("DELETE FROM trackers WHERE channel_id = ?", (channel_id,))
        self.conn.execute("DELETE FROM tracker_state WHERE channel_id = ?", (channel_id,))
        self.conn.commit()
        return cur.rowcount

    def list_trackers(self) -> list[TrackerRow]:
        rows = self.conn.execute(
            "SELECT guild_id, channel_id, user_id, username, ruleset FROM trackers ORDER BY channel_id"
        ).fetchall()
        return [
            TrackerRow(
                guild_id=int(r["guild_id"]),
                channel_id=int(r["channel_id"]),
                user_id=int(r["user_id"]),
                username=str(r["username"]),
                ruleset=str(r["ruleset"]),
            )
            for r in rows
        ]

    def get_state(self, channel_id: int) -> TrackerState:
        row = self.conn.execute(
            """SELECT snapshot_json, recent_score_ids_json, account_issue,
                      last_play_time, pending_snapshot_json, pending_changes_json
               FROM tracker_state WHERE channel_id = ?""",
            (channel_id,),
        ).fetchone()
        if row is None:
            return TrackerState(
                snapshot=None, recent_score_ids=[], account_issue=None,
                last_play_time=None, pending_snapshot=None, pending_changes=None,
            )
        return TrackerState(
            snapshot=json.loads(row["snapshot_json"]) if row["snapshot_json"] else None,
            recent_score_ids=json.loads(row["recent_score_ids_json"]) if row["recent_score_ids_json"] else [],
            account_issue=row["account_issue"],
            last_play_time=row["last_play_time"],
            pending_snapshot=json.loads(row["pending_snapshot_json"]) if row["pending_snapshot_json"] else None,
            pending_changes=json.loads(row["pending_changes_json"]) if row["pending_changes_json"] else None,
        )

    def put_state(
        self,
        channel_id: int,
        *,
        snapshot: dict[str, Any] | None,
        recent_score_ids: list[str],
        account_issue: str | None,
        last_play_time: float | None = None,
        pending_snapshot: dict[str, Any] | None = None,
        pending_changes: list[dict[str, Any]] | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO tracker_state(
                channel_id, snapshot_json, recent_score_ids_json, account_issue,
                last_play_time, pending_snapshot_json, pending_changes_json, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(channel_id) DO UPDATE SET
                snapshot_json=excluded.snapshot_json,
                recent_score_ids_json=excluded.recent_score_ids_json,
                account_issue=excluded.account_issue,
                last_play_time=excluded.last_play_time,
                pending_snapshot_json=excluded.pending_snapshot_json,
                pending_changes_json=excluded.pending_changes_json,
                updated_at=datetime('now')
            """,
            (
                channel_id,
                json.dumps(snapshot) if snapshot is not None else None,
                json.dumps(recent_score_ids),
                account_issue,
                last_play_time,
                json.dumps(pending_snapshot) if pending_snapshot is not None else None,
                json.dumps(pending_changes) if pending_changes is not None else None,
            ),
        )
        self.conn.commit()