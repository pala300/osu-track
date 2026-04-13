from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

import discord

COLOR_EMBED = 0xA8C3FB
EMOJI_UP = "<:up:1492849554008051763>"
EMOJI_DOWN = "<:down:1492849551680339978>"
EMOJI_PP = "<:pp:1492850011724316823>"
LOWER_IS_BETTER = {"global_rank", "country_rank"}

TRACKED_STATS = {
    "global_rank": "Global Rank",
    "country_rank": "Country Rank",
    "pp": "Performance Points",
    "hit_accuracy": "Hit Accuracy",
    "play_count": "Play Count",
    "ranked_score": "Ranked Score",
    "total_score": "Total Score",
    "maximum_combo": "Maximum Combo",
    "medals_count": "Medal Count",
}


def extract_stats(user: dict[str, Any]) -> dict[str, Any]:
    stats = user.get("statistics", {})
    country = user.get("country") or {}
    cc = (country.get("code") or "").strip().upper()
    if len(cc) != 2 or not cc.isalpha():
        cc = ""
    team = user.get("team") if isinstance(user.get("team"), dict) else {}
    team_name = (team.get("name") or team.get("short_name") or "").strip()
    return {
        "global_rank": stats.get("global_rank") or stats.get("rank", {}).get("global"),
        "country_rank": stats.get("country_rank") or stats.get("rank", {}).get("country"),
        "pp": round(stats.get("pp", 0), 2),
        "hit_accuracy": round(stats.get("hit_accuracy", 0), 2),
        "play_count": stats.get("play_count", 0),
        "ranked_score": stats.get("ranked_score", 0),
        "total_score": stats.get("total_score", 0),
        "maximum_combo": stats.get("maximum_combo", 0),
        "medals_count": len(user.get("user_achievements", [])),
        "_username": user.get("username", str(user.get("id", ""))),
        "_avatar_url": user.get("avatar_url", ""),
        "_timestamp": datetime.now(timezone.utc).isoformat(),
        "_country_code": cc,
        "_team_name": team_name,
    }


def account_issue(user: dict[str, Any] | None, not_found: bool = False) -> str | None:
    if not_found or not user:
        return "not_found"
    if user.get("is_deleted"):
        return "deleted"
    if user.get("is_restricted"):
        return "restricted"
    return None


def diff_stats(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key, label in TRACKED_STATS.items():
        ov = old.get(key)
        nv = new.get(key)
        if ov is None or nv is None or ov == nv:
            continue
        delta = nv - ov
        improved = delta < 0 if key in LOWER_IS_BETTER else delta > 0
        changes.append({"key": key, "label": label, "old": ov, "new": nv, "delta": delta, "improved": improved})
    return changes


def fmt(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if key in {"global_rank", "country_rank"}:
        return f"#{value:,}"
    if key == "hit_accuracy":
        return f"{value:.2f}%"
    if key == "pp":
        return f"{value:,}pp"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def fmt_delta(key: str, delta: Any) -> str:
    if delta == 0:
        return "±0"
    prefix = "+" if delta > 0 else ""
    if key in {"hit_accuracy"}:
        return f"{prefix}{delta:.2f}%"
    if key == "pp":
        return f"{prefix}{delta:,}pp"
    return f"{prefix}{delta:,}" if isinstance(delta, int) else f"{prefix}{delta}"


def _country_emoji(code: str) -> str:
    if len(code) != 2 or not code.isalpha():
        return ""
    a, b = code.upper()
    return chr(0x1F1E6 + ord(a) - ord("A")) + chr(0x1F1E6 + ord(b) - ord("A"))


def _country_label(stats: dict[str, Any]) -> str:
    bits: list[str] = []
    ce = _country_emoji(stats.get("_country_code", ""))
    if ce:
        bits.append(ce)
    team = (stats.get("_team_name") or "").strip()
    if team:
        bits.append(team)
    return f"{' '.join(bits)} · country rank" if bits else "country rank"


def build_first_embed(user_id: int, ruleset: str, stats: dict[str, Any]) -> discord.Embed:
    lines: list[str] = []
    for key, label in TRACKED_STATS.items():
        name = _country_label(stats) if key == "country_rank" else label.lower()
        lines.append(f"{name} · `{fmt(key, stats.get(key))}`")
    em = discord.Embed(
        title=f"{EMOJI_PP} Now tracking {stats['_username']}",
        description=f">>> baseline · {ruleset}\n\n" + "\n".join(lines),
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if stats.get("_avatar_url"):
        em.set_thumbnail(url=stats["_avatar_url"])
    em.set_footer(text="osu · tracker")
    return em


def build_change_embed(user_id: int, ruleset: str, stats: dict[str, Any], changes: list[dict[str, Any]]) -> discord.Embed:
    lines = [f">>> `{len(changes)}` update{'s' if len(changes) != 1 else ''} · {ruleset}", ""]
    for ch in changes:
        arrow = EMOJI_UP if ch["improved"] else EMOJI_DOWN
        label = _country_label(stats) if ch["key"] == "country_rank" else ch["label"].lower()
        lines.append(f"{arrow} {label} · `{fmt(ch['key'], ch['old'])}` → `{fmt(ch['key'], ch['new'])}` · `{fmt_delta(ch['key'], ch['delta'])}`")
    ts = stats["_timestamp"][:19].replace("T", " ")
    lines.extend(["", f"`{ts}` UTC"])
    em = discord.Embed(
        title=f"{EMOJI_PP} {stats['_username']}",
        description="\n".join(lines),
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if stats.get("_avatar_url"):
        em.set_thumbnail(url=stats["_avatar_url"])
    em.set_footer(text="osu · tracker")
    return em


def build_medal_embed(user_id: int, ruleset: str, stats: dict[str, Any], old_medals: int, new_medals: int) -> discord.Embed:
    earned = new_medals - old_medals
    em = discord.Embed(
        title=f"{EMOJI_PP} {stats['_username']}",
        description=f">>> `{earned}` new medal{'s' if earned != 1 else ''}\n\ntotal · `{old_medals}` → `{new_medals}`",
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if stats.get("_avatar_url"):
        em.set_thumbnail(url=stats["_avatar_url"])
    em.set_footer(text="osu · medals")
    return em


def build_issue_embed(user_id: int, ruleset: str, username: str, issue: str, avatar_url: str) -> discord.Embed:
    labels = {
        "not_found": "profile not found (404) — removed, renamed, or hidden from API",
        "restricted": "account restricted (`is_restricted`) — osu ban state",
        "deleted": "account deleted (`is_deleted`)",
    }
    em = discord.Embed(
        title=f"{EMOJI_PP} {username}",
        description=f">>> `{issue}`\n\n{labels.get(issue, issue)}",
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if avatar_url:
        em.set_thumbnail(url=avatar_url)
    em.set_footer(text="osu · account")
    return em


def build_recovered_embed(user_id: int, ruleset: str, username: str, avatar_url: str) -> discord.Embed:
    em = discord.Embed(
        title=f"{EMOJI_PP} {username}",
        description=">>> profile available again\n\n`is_restricted` / `is_deleted` cleared; tracking resumed.",
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if avatar_url:
        em.set_thumbnail(url=avatar_url)
    em.set_footer(text="osu · account")
    return em


def score_fingerprint(score: dict[str, Any]) -> str:
    sid = score.get("id")
    if sid is not None:
        return str(sid)
    lid = score.get("legacy_score_id")
    return f"L{lid}" if lid is not None else ""


def format_score_mods(mods: Any) -> str:
    if not mods:
        return "NM"
    out: list[str] = []
    for m in mods:
        if isinstance(m, dict):
            out.append(m.get("acronym") or "")
        else:
            out.append(str(m))
    return "".join(out) or "NM"


def _acc(acc: Any) -> str:
    try:
        val = float(acc)
    except (TypeError, ValueError):
        return "—"
    if val <= 1:
        val *= 100
    return f"{val:.2f}%"


def _score_link(score: dict[str, Any], ruleset: str) -> str | None:
    legacy_id = score.get("legacy_score_id")
    if legacy_id:
        return f"https://osu.ppy.sh/scores/{ruleset}/{legacy_id}"
    score_id = score.get("id")
    if score_id:
        return f"https://osu.ppy.sh/scores/{score_id}"
    return None


def _num(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _pick_number(score: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in score and score.get(k) is not None:
            return score.get(k)
    return None


def build_recent_play_embed(
    score: dict[str, Any],
    user_id: int,
    ruleset: str,
    username: str,
    avatar_url: str,
    current_pp: Any,
) -> tuple[discord.Embed, discord.ui.View | None]:
    bm = score.get("beatmap") or {}
    bs = score.get("beatmapset") or {}
    artist = html.unescape(bs.get("artist") or "—")
    title = html.unescape(bs.get("title") or "—")
    diff = html.unescape(bm.get("version") or "—")
    pp = score.get("pp")
    pp_s = f"{pp:.2f}pp" if pp is not None else "—"
    total_pp_s = f"{float(current_pp):,.2f}pp" if current_pp is not None else "—"
    rank = str(score.get("rank") or "?")
    combo = score.get("max_combo")
    combo_s = f"{combo:,}" if isinstance(combo, int) else "—"
    total_score_s = _num(_pick_number(score, "total_score", "classic_total_score", "legacy_total_score", "score"))
    rank_global = _pick_number(score, "rank_global", "position")
    rank_global_s = f"#{int(rank_global):,}" if isinstance(rank_global, int) else "—"
    stars = bm.get("difficulty_rating")
    stars_s = f" · `{stars:.2f}`★" if isinstance(stars, (int, float)) else ""
    bid = bm.get("id")
    ended = str(score.get("ended_at") or score.get("created_at") or "—")
    ts = ended[:19].replace("T", " ") if "T" in ended else ended
    stat = score.get("statistics") if isinstance(score.get("statistics"), dict) else {}
    c300 = _num(stat.get("great") if "great" in stat else stat.get("count_300"))
    c100 = _num(stat.get("ok") if "ok" in stat else stat.get("count_100"))
    c50 = _num(stat.get("meh") if "meh" in stat else stat.get("count_50"))
    cmiss = _num(stat.get("miss") if "miss" in stat else stat.get("count_miss"))
    description = (
        f">>> `{rank}` · `{pp_s}` · `{_acc(score.get('accuracy'))}` · `{format_score_mods(score.get('mods'))}`\n\n"
        f"{artist} — {title}\n"
        f"`{diff}`{stars_s}\n\n"
        f"profile pp · `{total_pp_s}`\n"
        f"score · `{total_score_s}`\n"
        f"global lb · `{rank_global_s}`\n"
        f"combo · `{combo_s}`\n"
        f"300/100/50/miss · `{c300}`/`{c100}`/`{c50}`/`{cmiss}`\n"
        f"`{ts}` UTC"
    )
    score_link = _score_link(score, ruleset)
    replay_link = f"{score_link}/download" if score_link and score.get("has_replay") else None
    em = discord.Embed(
        title=f"{EMOJI_PP} {username}",
        description=description,
        color=COLOR_EMBED,
        url=score_link or (f"https://osu.ppy.sh/beatmaps/{bid}" if bid else f"https://osu.ppy.sh/users/{user_id}/{ruleset}"),
    )
    cover = (bs.get("covers") or {}).get("list")
    if cover:
        em.set_thumbnail(url=cover)
    elif avatar_url:
        em.set_thumbnail(url=avatar_url)
    em.set_footer(text=f"osu · recent · {ruleset}")
    view: discord.ui.View | None = None
    if score_link or replay_link:
        view = discord.ui.View(timeout=None)
        if score_link:
            view.add_item(discord.ui.Button(label="Open Score", url=score_link))
        if replay_link:
            view.add_item(discord.ui.Button(label="Download Replay", url=replay_link))
    return em, view
