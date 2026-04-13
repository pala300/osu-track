from __future__ import annotations

import logging
import re
from typing import Any

import discord
import requests

from .config import Settings
from .db import TrackerDB, TrackerRow
from .embeds import (
    account_issue,
    build_change_embed,
    build_first_embed,
    build_issue_embed,
    build_medal_embed,
    build_recent_play_embed,
    build_recovered_embed,
    diff_stats,
    extract_stats,
    score_fingerprint,
)
from .osu_api import OsuApi

log = logging.getLogger(__name__)


def safe_channel_name(username: str, user_id: int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", username.strip().lower()).strip("-")
    slug = slug[:70] if slug else "osu-user"
    return f"{slug}-{user_id}"[:100]


class TrackerService:
    def __init__(self, bot: discord.Client, settings: Settings, db: TrackerDB, api: OsuApi) -> None:
        self.bot = bot
        self.settings = settings
        self.db = db
        self.api = api

    async def poll_once(self) -> None:
        for tr in self.db.list_trackers():
            await self._process_tracker(tr)

    async def _process_tracker(self, tr: TrackerRow) -> None:
        channel = self.bot.get_channel(tr.channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Channel %s missing; deleting tracker.", tr.channel_id)
            self.db.remove_tracker(tr.channel_id)
            return
        state = self.db.get_state(tr.channel_id)

        try:
            user = self.api.fetch_user_by_id(tr.user_id, tr.ruleset)
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            if code == 404:
                await self._handle_account_issue(channel, tr, state, "not_found", state.snapshot or {})
                return
            raise

        issue = account_issue(user)
        if issue:
            await self._handle_account_issue(channel, tr, state, issue, user)
            return

        if self.settings.notify_account_issues and state.account_issue:
            await channel.send(embed=build_recovered_embed(tr.user_id, tr.ruleset, user.get("username", str(tr.user_id)), user.get("avatar_url", "")))

        stats = extract_stats(user)
        recent_ids = state.recent_score_ids

        if self.settings.notify_recent_plays:
            scores = self.api.fetch_recent_scores(tr.user_id, tr.ruleset, self.settings.recent_scores_limit)
            if not recent_ids:
                recent_ids = [fp for fp in (score_fingerprint(s) for s in scores) if fp][: self.settings.recent_score_id_cap]
            else:
                seen = set(recent_ids)
                fresh: list[dict[str, Any]] = []
                for s in scores:
                    fp = score_fingerprint(s)
                    if not fp:
                        continue
                    if fp not in seen:
                        fresh.append(s)
                        recent_ids.append(fp)
                        seen.add(fp)
                while len(recent_ids) > self.settings.recent_score_id_cap:
                    recent_ids.pop(0)
                for s in reversed(fresh):
                    detailed = None
                    try:
                        detailed = self.api.fetch_score_details(s, tr.ruleset)
                    except Exception:
                        log.debug("Could not fetch score details for %s", score_fingerprint(s), exc_info=True)
                    rich_score = detailed or s
                    recent_embed, recent_view = build_recent_play_embed(
                        rich_score,
                        tr.user_id,
                        tr.ruleset,
                        stats["_username"],
                        stats["_avatar_url"],
                        stats.get("pp"),
                    )
                    await channel.send(
                        embed=recent_embed,
                        view=recent_view,
                    )

        if state.snapshot is None:
            await channel.send(embed=build_first_embed(tr.user_id, tr.ruleset, stats))
            self.db.put_state(tr.channel_id, snapshot=stats, recent_score_ids=recent_ids, account_issue=None)
            return

        changes = diff_stats(state.snapshot, stats)
        if not changes:
            self.db.put_state(tr.channel_id, snapshot=stats, recent_score_ids=recent_ids, account_issue=None)
            return

        old_medals = state.snapshot.get("medals_count", 0)
        new_medals = stats.get("medals_count", 0)
        if isinstance(old_medals, int) and isinstance(new_medals, int) and new_medals > old_medals:
            await channel.send(embed=build_medal_embed(tr.user_id, tr.ruleset, stats, old_medals, new_medals))
        await channel.send(embed=build_change_embed(tr.user_id, tr.ruleset, stats, changes))
        self.db.put_state(tr.channel_id, snapshot=stats, recent_score_ids=recent_ids, account_issue=None)

    async def _handle_account_issue(
        self,
        channel: discord.TextChannel,
        tr: TrackerRow,
        state: Any,
        issue: str,
        user_obj: dict[str, Any],
    ) -> None:
        username = user_obj.get("username") or (state.snapshot or {}).get("_username") or str(tr.user_id)
        avatar = user_obj.get("avatar_url") or (state.snapshot or {}).get("_avatar_url") or ""
        if self.settings.notify_account_issues and state.account_issue != issue:
            await channel.send(embed=build_issue_embed(tr.user_id, tr.ruleset, username, issue, avatar))
        self.db.put_state(
            tr.channel_id,
            snapshot=state.snapshot,
            recent_score_ids=state.recent_score_ids,
            account_issue=issue,
        )
