from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import discord
import requests
from discord import app_commands
from discord.ext import commands

from .config import Settings
from .db import TrackerDB
from .embeds import build_recent_play_embed
from .osu_api import OsuApi
from .tracker_service import TrackerService, safe_channel_name

log = logging.getLogger(__name__)

_RULESET_MAP: dict[int, str] = {0: "osu", 1: "taiko", 2: "fruits", 3: "mania"}


def _score_ruleset(score: dict[str, Any], default: str) -> str:
    return _RULESET_MAP.get(score.get("ruleset_id"), default)


def _mods(score: dict[str, Any]) -> list[str]:
    return [m.get("acronym") for m in (score.get("mods") or []) if isinstance(m, dict)]


async def _fetch_score_extras(
    loop: asyncio.AbstractEventLoop,
    api: OsuApi,
    bid: int,
    ruleset: str,
    mods: list[str],
) -> tuple[float | None, int | None]:
    max_pp, bm_data = await asyncio.gather(
        loop.run_in_executor(None, api.fetch_beatmap_max_pp, bid, ruleset, mods or None),
        loop.run_in_executor(None, api.fetch_beatmap, bid),
        return_exceptions=True,
    )
    fc_combo = None
    if isinstance(bm_data, dict):
        fc_combo = bm_data.get("max_combo")
    return (max_pp if isinstance(max_pp, float) else None, fc_combo)


def create_bot(settings: Settings, db: TrackerDB, api: OsuApi) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True

    bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents)
    service = TrackerService(bot, settings, db, api)

    @bot.event
    async def on_ready() -> None:
        log.info("Bot ready as %s (%s)", bot.user, bot.user.id if bot.user else "?")
        try:
            synced = await bot.tree.sync()
            log.info("Synced %d slash commands", len(synced))
        except Exception as e:
            log.exception("Failed to sync commands: %s", e)
        bot.loop.create_task(poll_loop())

    async def poll_loop() -> None:
        await bot.wait_until_ready()
        while not bot.is_closed():
            try:
                await service.poll_once()
            except Exception:
                log.exception("Polling loop failed")
            await asyncio.sleep(settings.poll_interval)

    def _admin_only() -> commands.check:
        async def predicate(ctx: commands.Context) -> bool:
            perms = getattr(ctx.author, "guild_permissions", None)
            return bool(perms and perms.administrator)
        return commands.check(predicate)

    @bot.command(name="track")
    @_admin_only()
    async def track(ctx: commands.Context, channel_id: int, osu_username: str) -> None:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await ctx.reply("Channel must be a text channel.")
            return
        if ctx.guild is None or channel.guild.id != ctx.guild.id:
            await ctx.reply("Channel must be in this server.")
            return
        query = osu_username.strip()
        try:
            user = api.fetch_user_by_id(int(query), settings.default_ruleset) if query.isdigit() else api.fetch_user_by_username(query, settings.default_ruleset)
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            await ctx.reply(f"Could not resolve osu user `{query}` (HTTP {code}).")
            return

        user_id = int(user["id"])
        username = str(user.get("username", osu_username))
        db.upsert_tracker(ctx.guild.id, channel.id, user_id, username, settings.default_ruleset)
        db.put_state(
            channel.id,
            snapshot=None,
            recent_score_ids=[],
            account_issue=None,
            last_play_time=None,
            pending_snapshot=None,
            pending_changes=None,
        )

        new_name = safe_channel_name(username, user_id)
        try:
            await channel.edit(name=new_name, reason=f"Tracking osu user {username}")
        except discord.Forbidden:
            await ctx.reply(f"Tracking added, but I couldn't rename <#{channel.id}>.")
            return

        await ctx.reply(f"Now tracking `{username}` (`{user_id}`) in <#{channel.id}>.")

    @bot.command(name="untrack")
    @_admin_only()
    async def untrack(ctx: commands.Context, channel_id: int) -> None:
        count = db.remove_tracker(channel_id)
        if count:
            await ctx.reply(f"Stopped tracking for <#{channel_id}>.")
        else:
            await ctx.reply("No tracker found for that channel.")

    @bot.command(name="tracks")
    @_admin_only()
    async def tracks(ctx: commands.Context) -> None:
        if ctx.guild is None:
            await ctx.reply("Use this in a server.")
            return
        rows = [r for r in db.list_trackers() if r.guild_id == ctx.guild.id]
        if not rows:
            await ctx.reply("No trackers configured in this server.")
            return
        msg = "\n".join(
            f"- <#{r.channel_id}> → `{r.username}` (`{r.user_id}`) · `{r.ruleset}`"
            for r in rows
        )
        await ctx.reply(msg)

    @bot.tree.command(name="link", description="Link your Discord account to your osu! username")
    @app_commands.describe(username="Your osu! username")
    async def link_command(interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            user = await bot.loop.run_in_executor(None, api.fetch_user_by_username, username.strip(), settings.default_ruleset)
        except Exception:
            await interaction.followup.send(f"Could not find osu! user `{username.strip()}`.")
            return
        osu_username = str(user.get("username", username.strip()))
        db.link_user(interaction.user.id, osu_username)
        await interaction.followup.send(f"Linked your Discord to osu! user **{osu_username}**.")

    @bot.tree.command(name="unlink", description="Unlink your Discord account from your osu! username")
    async def unlink_command(interaction: discord.Interaction) -> None:
        linked = db.get_linked_user(interaction.user.id)
        if not linked:
            await interaction.response.send_message("You don't have a linked osu! account.", ephemeral=True)
            return
        db.unlink_user(interaction.user.id)
        await interaction.response.send_message(f"Unlinked from **{linked}**.", ephemeral=True)

    @bot.tree.command(name="rs", description="Show your most recent score")
    @app_commands.describe(username="osu! username (uses your linked account if omitted)")
    async def rs_command(interaction: discord.Interaction, username: str | None = None) -> None:
        await interaction.response.defer()
        try:
            target = username or db.get_linked_user(interaction.user.id)
            if not target:
                await interaction.followup.send("No linked account. Use `/link <username>` first, or pass a username.")
                return

            user = await bot.loop.run_in_executor(None, api.fetch_user_by_username, target, settings.default_ruleset)
            scores = await bot.loop.run_in_executor(None, api.fetch_recent_scores, int(user["id"]), settings.default_ruleset, 1)
            if not scores:
                await interaction.followup.send(f"No recent scores found for **{user.get('username')}**.")
                return

            score = scores[0]
            bid = (score.get("beatmap") or {}).get("id")
            ruleset = _score_ruleset(score, settings.default_ruleset)
            max_pp, fc_combo = await _fetch_score_extras(bot.loop, api, bid, ruleset, _mods(score)) if bid else (None, None)

            embed, view = build_recent_play_embed(score, int(user["id"]), ruleset, user.get("username", target), user.get("avatar_url", ""), max_pp=max_pp, fc_combo=fc_combo)
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            log.exception("Error in /rs command")
            await interaction.followup.send("Something went wrong. Please try again.")

    @bot.tree.command(name="bt", description="Show your best score from today")
    @app_commands.describe(username="osu! username (uses your linked account if omitted)")
    async def bt_command(interaction: discord.Interaction, username: str | None = None) -> None:
        await interaction.response.defer()
        try:
            target = username or db.get_linked_user(interaction.user.id)
            if not target:
                await interaction.followup.send("No linked account. Use `/link <username>` first, or pass a username.")
                return

            user = await bot.loop.run_in_executor(None, api.fetch_user_by_username, target, settings.default_ruleset)
            scores = await bot.loop.run_in_executor(None, api.fetch_recent_scores, int(user["id"]), settings.default_ruleset, 50)
            if not scores:
                await interaction.followup.send(f"No recent scores found for **{user.get('username')}**.")
                return

            today = datetime.now(timezone.utc).date()
            today_scores = [
                s for s in scores
                if (ts := s.get("ended_at") or s.get("created_at"))
                and _parse_date(ts) == today
            ]
            if not today_scores:
                await interaction.followup.send(f"No scores from today for **{user.get('username')}**.")
                return

            score = max(today_scores, key=lambda s: s.get("pp") or 0)
            bid = (score.get("beatmap") or {}).get("id")
            ruleset = _score_ruleset(score, settings.default_ruleset)
            max_pp, fc_combo = await _fetch_score_extras(bot.loop, api, bid, ruleset, _mods(score)) if bid else (None, None)

            embed, view = build_recent_play_embed(score, int(user["id"]), ruleset, user.get("username", target), user.get("avatar_url", ""), max_pp=max_pp, fc_combo=fc_combo)
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            log.exception("Error in /bt command")
            await interaction.followup.send("Something went wrong. Please try again.")

    @track.error
    @untrack.error
    @tracks.error
    async def _admin_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CheckFailure):
            await ctx.reply("Admin only.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Usage: `{settings.command_prefix}{ctx.command.name} {ctx.command.signature}`")
            return
        raise error

    return bot


def _parse_date(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
    except Exception:
        return None
