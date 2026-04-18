from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TrackerRow:
    guild_id: int
    channel_id: int
    user_id: int
    username: str
    ruleset: str


@dataclass
class StateRow:
    channel_id: int
    snapshot: dict[str, Any] | None
    recent_score_ids: list[str]
    account_issue: str | None
    last_play_time: float | None
    pending_snapshot: dict[str, Any] | None
    pending_changes: list[dict[str, Any]] | None


class TrackerDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._setup()

    def _setup(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trackers (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    ruleset TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    channel_id INTEGER PRIMARY KEY,
                    snapshot TEXT,
                    recent_score_ids TEXT,
                    account_issue TEXT,
                    last_play_time REAL,
                    pending_snapshot TEXT,
                    pending_changes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_links (
                    discord_id INTEGER PRIMARY KEY,
                    osu_username TEXT NOT NULL,
                    osu_user_id INTEGER
                )
            """)
            conn.commit()
            self._migrate()

    def _migrate(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            state_cols = {row[1] for row in conn.execute("PRAGMA table_info(state)")}
            if "last_play_time" not in state_cols:
                conn.execute("ALTER TABLE state ADD COLUMN last_play_time REAL")
            if "pending_snapshot" not in state_cols:
                conn.execute("ALTER TABLE state ADD COLUMN pending_snapshot TEXT")
            if "pending_changes" not in state_cols:
                conn.execute("ALTER TABLE state ADD COLUMN pending_changes TEXT")
            link_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_links)")}
            if "osu_user_id" not in link_cols:
                conn.execute("ALTER TABLE user_links ADD COLUMN osu_user_id INTEGER")
            conn.commit()

    def upsert_tracker(self, guild_id: int, channel_id: int, user_id: int, username: str, ruleset: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO trackers (guild_id, channel_id, user_id, username, ruleset) VALUES (?, ?, ?, ?, ?)",
                (guild_id, channel_id, user_id, username, ruleset),
            )
            conn.commit()

    def remove_tracker(self, channel_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM trackers WHERE channel_id = ?", (channel_id,))
            conn.execute("DELETE FROM state WHERE channel_id = ?", (channel_id,))
            conn.commit()
            return cur.rowcount

    def list_trackers(self) -> list[TrackerRow]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT guild_id, channel_id, user_id, username, ruleset FROM trackers").fetchall()
            return [TrackerRow(*r) for r in rows]

    def get_state(self, channel_id: int) -> StateRow:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT snapshot, recent_score_ids, account_issue, last_play_time, pending_snapshot, pending_changes FROM state WHERE channel_id = ?", (channel_id,)).fetchone()
            if not row:
                return StateRow(channel_id, None, [], None, None, None, None)
            snap = json.loads(row[0]) if row[0] else None
            ids = json.loads(row[1]) if row[1] else []
            issue = row[2]
            last_play = row[3]
            pend_snap = json.loads(row[4]) if row[4] else None
            pend_chg = json.loads(row[5]) if row[5] else None
            return StateRow(channel_id, snap, ids, issue, last_play, pend_snap, pend_chg)

    def put_state(
        self,
        channel_id: int,
        snapshot: dict[str, Any] | None,
        recent_score_ids: list[str],
        account_issue: str | None,
        last_play_time: float | None = None,
        pending_snapshot: dict[str, Any] | None = None,
        pending_changes: list[dict[str, Any]] | None = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO state (channel_id, snapshot, recent_score_ids, account_issue, last_play_time, pending_snapshot, pending_changes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel_id,
                    json.dumps(snapshot) if snapshot else None,
                    json.dumps(recent_score_ids),
                    account_issue,
                    last_play_time,
                    json.dumps(pending_snapshot) if pending_snapshot else None,
                    json.dumps(pending_changes) if pending_changes else None,
                ),
            )
            conn.commit()

    def link_user(self, discord_id: int, osu_username: str, osu_user_id: int | None = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_links (discord_id, osu_username, osu_user_id) VALUES (?, ?, ?)",
                (discord_id, osu_username, osu_user_id),
            )
            conn.commit()

    def list_linked_users(self) -> list[tuple[str, int]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT osu_username, osu_user_id FROM user_links WHERE osu_user_id IS NOT NULL"
            ).fetchall()
            return [(row[0], row[1]) for row in rows]

    def unlink_user(self, discord_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_links WHERE discord_id = ?", (discord_id,))
            conn.commit()

    def get_linked_user(self, discord_id: int) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT osu_username FROM user_links WHERE discord_id = ?", (discord_id,)).fetchone()
            return row[0] if row else None

