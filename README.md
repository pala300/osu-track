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

### discord invite
replace `YOUR_BOT_CLIENT_ID` with your bot's client ID from discord developer portal
```
https://discord.com/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=68608&scope=bot%20applications.commands
```

### user commands 
- `/link <username>` - link your discord to your osu username to bypass entering your own [username] in commands.
- `/unlink` - unlink your discord from your osu account.
- `/rs [username]` - show user's recently submitted score.
- `/bt [username]` - show user's highest pp play of the day.
- `/map <beatmap>` - show all tracked server scores on a beatmap (url or id).
- `/help` - show available commands.

### admin commands
- `!track <channel_id> <osu_username_or_id>`
- `!untrack <channel_id>`
- `!tracks`

when you track someone, the bot renames the channel to `username-id` and sends updates there.

