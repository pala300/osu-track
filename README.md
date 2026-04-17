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

## discord invite
```
https://discord.com/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=68608&scope=bot%20applications.commands
```
(replace `YOUR_BOT_CLIENT_ID` with your bot's client ID from discord developer portal)

### admin commands
- `!track <channel_id> <osu_username_or_id>`
- `!untrack <channel_id>`
- `!tracks`

when you track someone, the bot renames the channel to `username-id` and sends updates there.

### slash commands (everyone)
- `/link <username>` - link your discord to your osu username
- `/rs [username]` - show recent score (yours if linked, or specify username)
- `/bt [username]` - show best score today (yours if linked, or specify username)
