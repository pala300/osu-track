#!/usr/bin/env python3

import logging

from osu_bot.bot import create_bot
from osu_bot.config import load_settings
from osu_bot.db import TrackerDB
from osu_bot.osu_api import OsuApi


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.log_file, encoding="utf-8"),
        ],
    )
    if not settings.discord_token:
        raise SystemExit("DISCORD_BOT_TOKEN is required.")
    if not settings.osu_client_id or not settings.osu_client_secret:
        raise SystemExit("OSU_CLIENT_ID and OSU_CLIENT_SECRET are required.")
    db = TrackerDB(settings.db_path)
    api = OsuApi(settings.osu_client_id, settings.osu_client_secret)
    bot = create_bot(settings, db, api)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()