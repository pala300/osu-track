from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

import discord

COLOR_EMBED = 0xA8C3FB
EMOJI_UP    = "<:gaining:1493963445966737538>"
EMOJI_DOWN  = "<:losing:1493963501910364342>"
EMOJI_PP    = "<:pp:1492850011724316823>"

GRADE_EMOJI: dict[str, str] = {
    "XH": "<:rankingXH:1493945697005863034>",
    "X":  "<:rankingX:1493945770695462972>",
    "SH": "<:rankingSH:1493945829990334555>",
    "S":  "<:rankingS:1493945880607195239>",
    "A":  "<:rankingA:1493945917705949284>",
    "B":  "<:rankingB:1493945981912219769>",
    "C":  "<:rankingC:1493946002040819732>",
    "D":  "<:rankingD:1493946024203391088>",
}

HIT_EMOJI: dict[str, str] = {
    "300": "<:hit300:1493960871540555928>",
    "100": "<:hit100:1493960828096090202>",
    "50":  "<:hit50:1493960772303327373>",
    "0":   "<:hit0:1493960706330988796>",
}

MOD_EMOJI: dict[str, str] = {
    "SD": "<:selectionmodsuddendeath2x:1493946824954744832>",
    "SO": "<:selectionmodspunout2x:1493946793531015218>",
    "RX": "<:selectionmodrelax2x:1493946740288782446>",
    "AP": "<:selectionmodautoplay2x:1493946425439162551>",
    "PF": "<:selectionmodperfect2x:1493946709150007376>",
    "NF": "<:selectionmodnofail2x:1493946680393859165>",
    "NC": "<:selectionmodnightcore2x:1493946647481417748>",
    "HD": "<:selectionmodhidden2x:1493946599850901666>",
    "HR": "<:selectionmodhardrock2x:1493946570704420864>",
    "HT": "<:selectionmodhalftime2x:1493946549057884181>",
    "FL": "<:selectionmodflashlight2x:1493946519748087949>",
    "EZ": "<:selectionmodeasy2x:1493946483848904704>",
    "DT": "<:selectionmoddoubletime2x:1493946450181357720>",
}

LOWER_IS_BETTER = {"global_rank", "country_rank"}

TRACKED_STATS = {
    "global_rank":   "Global Rank",
    "country_rank":  "Country Rank",
    "pp":            "Performance Points",
    "hit_accuracy":  "Hit Accuracy",
    "play_count":    "Play Count",
    "ranked_score":  "Ranked Score",
    "total_score":   "Total Score",
    "maximum_combo": "Maximum Combo",
    "medals_count":  "Medal Count",
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
        "global_rank":   stats.get("global_rank") or stats.get("rank", {}).get("global"),
        "country_rank":  stats.get("country_rank") or stats.get("rank", {}).get("country"),
        "pp":            round(stats.get("pp", 0), 2),
        "hit_accuracy":  round(stats.get("hit_accuracy", 0), 2),
        "play_count":    stats.get("play_count", 0),
        "ranked_score":  stats.get("ranked_score", 0),
        "total_score":   stats.get("total_score", 0),
        "maximum_combo": stats.get("maximum_combo", 0),
        "medals_count":  len(user.get("user_achievements", [])),
        "_username":     user.get("username", str(user.get("id", ""))),
        "_avatar_url":   user.get("avatar_url", ""),
        "_timestamp":    datetime.now(timezone.utc).isoformat(),
        "_country_code": cc,
        "_team_name":    team_name,
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
    if key == "hit_accuracy":
        return f"{prefix}{delta:.2f}%"
    if key == "pp":
        return f"{prefix}{round(delta, 2):,}pp"
    return f"{prefix}{delta:,}" if isinstance(delta, int) else f"{prefix}{delta}"


def _country_emoji(code: str) -> str:
    if len(code) != 2 or not code.isalpha():
        return ""
    a, b = code.upper()
    return chr(0x1F1E6 + ord(a) - ord("A")) + chr(0x1F1E6 + ord(b) - ord("A"))


def _country_label(stats: dict[str, Any]) -> str:
    ce = _country_emoji(stats.get("_country_code", ""))
    return f"{ce} country rank" if ce else "country rank"


def _grade_emoji(rank: str) -> str:
    return GRADE_EMOJI.get(rank, f"`{rank}`")


def _fmt_mods(mods: Any) -> str:
    if not mods:
        return "`—`"
    acronyms = [m.get("acronym") if isinstance(m, dict) else str(m) for m in mods]
    acronyms = [a for a in acronyms if a]
    if not acronyms:
        return "`—`"
    return " ".join(MOD_EMOJI.get(a, f"`{a}`") for a in acronyms)


def _num(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


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


def score_fingerprint(score: dict[str, Any]) -> str:
    sid = score.get("id")
    if sid is not None:
        return str(sid)
    lid = score.get("legacy_score_id")
    return f"L{lid}" if lid is not None else ""


def build_first_embed(user_id: int, ruleset: str, stats: dict[str, Any]) -> discord.Embed:
    em = discord.Embed(
        title=f"{EMOJI_PP} now tracking {stats['_username']}",
        description=f"baseline snapshot · **{ruleset}**",
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if stats.get("_avatar_url"):
        em.set_thumbnail(url=stats["_avatar_url"])

    em.add_field(name="global rank",  value=f"`{fmt('global_rank',  stats.get('global_rank'))}`",   inline=True)
    em.add_field(name="country rank", value=f"`{fmt('country_rank', stats.get('country_rank'))}`",  inline=True)
    em.add_field(name="pp",           value=f"`{fmt('pp',           stats.get('pp'))}`",            inline=True)

    em.add_field(name="accuracy",     value=f"`{fmt('hit_accuracy', stats.get('hit_accuracy'))}`",  inline=True)
    em.add_field(name="play count",   value=f"`{fmt('play_count',   stats.get('play_count'))}`",    inline=True)
    em.add_field(name="max combo",    value=f"`{fmt('maximum_combo',stats.get('maximum_combo'))}`", inline=True)

    em.add_field(name="ranked score", value=f"`{fmt('ranked_score', stats.get('ranked_score'))}`",  inline=True)
    em.add_field(name="total score",  value=f"`{fmt('total_score',  stats.get('total_score'))}`",   inline=True)
    em.add_field(name="medals",       value=f"`{fmt('medals_count', stats.get('medals_count'))}`",  inline=True)

    em.set_footer(text="osu · tracker")
    return em


def build_change_embed(user_id: int, ruleset: str, stats: dict[str, Any], changes: list[dict[str, Any]]) -> discord.Embed:
    ts = stats["_timestamp"][:19].replace("T", " ")
    em = discord.Embed(
        title=f"{EMOJI_PP} {stats['_username']} — {len(changes)} update{'s' if len(changes) != 1 else ''}",
        description=f"**{ruleset}** · `{ts}` UTC",
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if stats.get("_avatar_url"):
        em.set_thumbnail(url=stats["_avatar_url"])

    for ch in changes:
        arrow = EMOJI_UP if ch["improved"] else EMOJI_DOWN
        label = _country_label(stats) if ch["key"] == "country_rank" else ch["label"].lower()
        value = f"`{fmt(ch['key'], ch['old'])}` → `{fmt(ch['key'], ch['new'])}` (`{fmt_delta(ch['key'], ch['delta'])}`)"
        em.add_field(name=f"{arrow} {label}", value=value, inline=False)

    em.set_footer(text="osu · tracker")
    return em


def build_medal_embed(user_id: int, ruleset: str, stats: dict[str, Any], old_medals: int, new_medals: int) -> discord.Embed:
    earned = new_medals - old_medals
    em = discord.Embed(
        title=f"🏅 {stats['_username']} unlocked {'a medal' if earned == 1 else f'{earned} medals'}!",
        description=f"**{old_medals}** → **{new_medals}** total medals",
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if stats.get("_avatar_url"):
        em.set_thumbnail(url=stats["_avatar_url"])
    em.set_footer(text="osu · medals")
    return em


def build_issue_embed(user_id: int, ruleset: str, username: str, issue: str, avatar_url: str) -> discord.Embed:
    labels = {
        "not_found":  "profile not found — removed, renamed, or hidden from api.",
        "restricted": "account restricted — osu! ban state.",
        "deleted":    "account deleted.",
    }
    em = discord.Embed(
        title=f"⚠️ {username}",
        description=labels.get(issue, issue),
        color=0xFF6B6B,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if avatar_url:
        em.set_thumbnail(url=avatar_url)
    em.set_footer(text="osu · account")
    return em


def build_recovered_embed(user_id: int, ruleset: str, username: str, avatar_url: str) -> discord.Embed:
    em = discord.Embed(
        title=f"✅ {username} — profile back online",
        description="restriction cleared. tracking resumed.",
        color=0x78C878,
        url=f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )
    if avatar_url:
        em.set_thumbnail(url=avatar_url)
    em.set_footer(text="osu · account")
    return em


def _format_score_line(i: int, entry: dict[str, Any], include_score: bool = True) -> str:
    s = entry["score"]
    grade = _grade_emoji(str(s.get("rank") or "?"))
    acc = _acc(s.get("accuracy"))
    pp = s.get("pp")
    pp_s = f"{pp:.0f}pp" if pp is not None else "—"
    combo = s.get("max_combo")
    combo_s = f"{combo:,}x" if isinstance(combo, int) else "—"
    mods_s = _fmt_mods(s.get("mods"))
    mods_part = f" · {mods_s}" if mods_s != "`—`" else ""
    line = f"`#{i}` {grade} **{entry['username']}** · {acc} · {pp_s} · {combo_s}{mods_part}"
    if include_score:
        total = next((s.get(k) for k in ("total_score", "classic_total_score", "score") if s.get(k)), None)
        line += f" · {_num(total)}"
    return line


def build_map_scores_embed(
    bm: dict[str, Any],
    entries: list[dict[str, Any]],
    max_pp: float | None,
    ruleset: str,
) -> discord.Embed:
    bs = bm.get("beatmapset") or {}
    artist = html.unescape(bs.get("artist") or "—")
    title = html.unescape(bs.get("title") or "—")
    diff = html.unescape(bm.get("version") or "—")
    stars = bm.get("difficulty_rating")
    stars_s = f"{stars:.2f}★" if isinstance(stars, (int, float)) else "—"
    bid = bm.get("id")
    max_combo = bm.get("max_combo")
    max_combo_s = f"{max_combo:,}x" if isinstance(max_combo, int) else "—"
    max_pp_s = f"{max_pp:.0f}pp" if max_pp is not None else "—"

    lines: list[str] = [f"{stars_s} · max combo: {max_combo_s} · max pp: {max_pp_s}\n"]
    if not entries:
        lines.append("no scores found.")
    else:
        lines.extend(_format_score_line(i, e) for i, e in enumerate(entries, 1))

    em = discord.Embed(
        title=f"{artist} — {title} [{diff}]",
        description="\n".join(lines),
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/beatmaps/{bid}" if bid else None,
    )
    covers = bs.get("covers") or {}
    cover = covers.get("list@2x") or covers.get("list")
    if cover:
        em.set_thumbnail(url=cover)
    em.set_footer(text=f"osu · map · {ruleset}")
    return em


def build_beatmapset_scores_embed(
    bs: dict[str, Any],
    diffs: list[dict[str, Any]],
    ruleset: str,
) -> discord.Embed:
    artist = html.unescape(bs.get("artist") or "—")
    title = html.unescape(bs.get("title") or "—")
    bsid = bs.get("id")

    sections: list[str] = []
    for d in diffs:
        bm = d["beatmap"]
        diff_name = html.unescape(bm.get("version") or "—")
        stars = bm.get("difficulty_rating")
        stars_s = f"{stars:.2f}★" if isinstance(stars, (int, float)) else "—"
        max_combo = bm.get("max_combo")
        max_combo_s = f" · max {max_combo:,}x" if isinstance(max_combo, int) else ""
        lines = [f"**[{diff_name}] · {stars_s}{max_combo_s}**"]
        lines.extend(_format_score_line(i, e, include_score=False) for i, e in enumerate(d["entries"], 1))
        sections.append("\n".join(lines))

    description = "\n\n".join(sections)
    if len(description) > 4096:
        description = description[:4090] + "\n…"

    em = discord.Embed(
        title=f"{artist} — {title}",
        description=description,
        color=COLOR_EMBED,
        url=f"https://osu.ppy.sh/beatmapsets/{bsid}" if bsid else None,
    )
    covers = bs.get("covers") or {}
    cover = covers.get("list@2x") or covers.get("list")
    if cover:
        em.set_thumbnail(url=cover)
    em.set_footer(text=f"osu · map · {ruleset}")
    return em


def build_recent_play_embed(
    score: dict[str, Any],
    user_id: int,
    ruleset: str,
    username: str,
    avatar_url: str,
    max_pp: float | None = None,
    fc_combo: int | None = None,
) -> tuple[discord.Embed, discord.ui.View | None]:
    bm      = score.get("beatmap") or {}
    bs      = score.get("beatmapset") or {}
    artist  = html.unescape(bs.get("artist") or "—")
    title   = html.unescape(bs.get("title") or "—")
    diff    = html.unescape(bm.get("version") or "—")
    stars   = bm.get("difficulty_rating")
    stars_s = f"{stars:.2f}★" if isinstance(stars, (int, float)) else "—"
    bid     = bm.get("id")

    pp = score.get("pp")
    if pp is not None and max_pp is not None:
        pp_s = f"{pp:.0f}/{max_pp:.0f}pp"
    elif pp is not None:
        pp_s = f"{pp:.2f}pp"
    else:
        pp_s = "—"

    rank    = str(score.get("rank") or "?")
    combo   = score.get("max_combo")
    combo_s = f"{combo:,}x" if isinstance(combo, int) else "—"
    combo_field = f"`{combo_s} / {fc_combo:,}x`" if isinstance(fc_combo, int) else f"`{combo_s}`"

    total_score_s = _num(
        next((score.get(k) for k in ("total_score", "classic_total_score", "legacy_total_score", "score") if score.get(k) is not None), None)
    )

    ended = str(score.get("ended_at") or score.get("created_at") or "—")
    ts    = ended[:19].replace("T", " ") if "T" in ended else ended

    stat  = score.get("statistics") if isinstance(score.get("statistics"), dict) else {}
    c300  = _num(stat.get("great") if "great" in stat else stat.get("count_300"))
    c100  = _num(stat.get("ok")    if "ok"    in stat else stat.get("count_100"))
    c50   = _num(stat.get("meh")   if "meh"   in stat else stat.get("count_50"))
    cmiss = _num(stat.get("miss")  if "miss"  in stat else stat.get("count_miss"))

    score_link  = _score_link(score, ruleset)
    replay_link = f"{score_link}/download" if score_link and score.get("has_replay") else None

    beatmap_url = f"https://osu.ppy.sh/beatmaps/{bid}" if bid else None
    song_text = f"[**{artist} — {title}**]({beatmap_url})" if beatmap_url else f"**{artist} — {title}**"

    em = discord.Embed(
        title=f"{EMOJI_PP} {username}",
        description=f"{song_text}\n{diff} · {stars_s} · {ruleset}",
        color=COLOR_EMBED,
        url=score_link or beatmap_url or f"https://osu.ppy.sh/users/{user_id}/{ruleset}",
    )

    em.add_field(name="pp",       value=f"`{pp_s}`",                        inline=True)
    em.add_field(name="grade",    value=_grade_emoji(rank),                 inline=True)
    em.add_field(name="\u200b",   value="\u200b",                           inline=True)

    em.add_field(name="accuracy", value=f"`{_acc(score.get('accuracy'))}`", inline=True)
    em.add_field(name="combo",    value=combo_field,                        inline=True)
    em.add_field(name="\u200b",   value="\u200b",                           inline=True)

    em.add_field(name="score",    value=f"`{total_score_s}`",               inline=True)
    em.add_field(name="mods",     value=_fmt_mods(score.get("mods")),       inline=True)
    em.add_field(name="\u200b",   value="\u200b",                           inline=True)

    hits = (
        f"{HIT_EMOJI['300']} `{c300}`  ·  "
        f"{HIT_EMOJI['100']} `{c100}`  ·  "
        f"{HIT_EMOJI['50']} `{c50}`  ·  "
        f"{HIT_EMOJI['0']} `{cmiss}`"
    )
    em.add_field(name="hits", value=hits, inline=False)

    covers     = bs.get("covers") or {}
    cover_list = covers.get("list@2x") or covers.get("list")
    if cover_list:
        em.set_thumbnail(url=cover_list)

    em.set_footer(text=f"{ts} UTC  ·  osu · recent · {ruleset}")

    view: discord.ui.View | None = None
    if score_link or replay_link:
        view = discord.ui.View(timeout=None)
        if score_link:
            view.add_item(discord.ui.Button(label="Open Score", url=score_link))
        if replay_link:
            view.add_item(discord.ui.Button(label="Download Replay", url=replay_link))
    return em, view