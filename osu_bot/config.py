from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    discord_token: str
    osu_client_id: int
    osu_client_secret: str
    poll_interval: int
    db_path: Path
    log_file: Path
    default_ruleset: str
    recent_scores_limit: int
    recent_score_id_cap: int
    notify_recent_plays: bool
    notify_account_issues: bool
    command_prefix: str


def load_settings() -> Settings:
    return Settings(
        discord_token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
        osu_client_id=int(os.getenv("OSU_CLIENT_ID", "0")),
        osu_client_secret=os.getenv("OSU_CLIENT_SECRET", "").strip(),
        poll_interval=max(5, int(os.getenv("POLL_INTERVAL", "300"))),
        db_path=Path(os.getenv("DB_PATH", "tracker.db")),
        log_file=Path(os.getenv("LOG_FILE", "osu_tracker.log")),
        default_ruleset=os.getenv("RULESET", "osu").strip() or "osu",
        recent_scores_limit=max(1, min(int(os.getenv("RECENT_SCORES_LIMIT", "25")), 50)),
        recent_score_id_cap=max(50, int(os.getenv("RECENT_SCORE_ID_CAP", "400"))),
        notify_recent_plays=_as_bool("NOTIFY_RECENT_PLAYS", True),
        notify_account_issues=_as_bool("NOTIFY_ACCOUNT_ISSUES", True),
        command_prefix=os.getenv("COMMAND_PREFIX", "!").strip() or "!",
    )
