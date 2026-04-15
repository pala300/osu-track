# osu!track

lite discord bot for tracking osu profiles in server channels.

it polls osu api, posts stat changes, recent plays, medal updates, and account status alerts.

## setup

1. copy `.env.example` to `.env`
2. fill `DISCORD_BOT_TOKEN`, `OSU_CLIENT_ID`, `OSU_CLIENT_SECRET`
3. install deps:
   `pip install -r requirements.txt`
4. run:
   `py main.py`

## commands (admin only)

- `!track <channel_id> <osu_username_or_id>`
- `!untrack <channel_id>`
- `!tracks`

when you track someone, the bot renames the channel to `username-id` and sends updates there.
