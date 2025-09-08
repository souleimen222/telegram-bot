import asyncio
from datetime import datetime, timezone
import subprocess
from sofascore_wrapper.api import SofascoreAPI
import aiohttp

PREMIER_LEAGUE_TEAMS = {
    "Manchester City", "Manchester United", "Liverpool", "Arsenal",
    "Chelsea", "Tottenham Hotspur", "Newcastle United", "Aston Villa",
    "Brighton & Hove Albion", "West Ham United", "Wolverhampton Wanderers",
    "Crystal Palace", "Fulham", "Brentford", "Everton", "Nottingham Forest",
    "Bournemouth", "Sunderland", "Leeds United", "Burnley"
}

# Patch aiohttp to always include a User-Agent
_orig_aiohttp_request = aiohttp.ClientSession._request

async def _patched_aiohttp_request(self, method, url, **kwargs):
    headers = kwargs.get("headers", {})
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    kwargs["headers"] = headers
    return await _orig_aiohttp_request(self, method, url, **kwargs)

aiohttp.ClientSession._request = _patched_aiohttp_request

async def check_pl_games():
    api = SofascoreAPI()
    try:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data = await api._get(f"/sport/football/scheduled-events/{date_str}")
        events = data.get("events", [])

        now_ts = int(datetime.now(timezone.utc).timestamp())
        time_window_seconds = 75 * 60

        for match in events:
            home = match.get("homeTeam", {}).get("name")
            away = match.get("awayTeam", {}).get("name")
            start_ts = match.get("startTimestamp")

            if not start_ts:
                continue

            if (home in PREMIER_LEAGUE_TEAMS or away in PREMIER_LEAGUE_TEAMS) and abs(start_ts - now_ts) <= time_window_seconds and start_ts >= now_ts:
                print(f"Premier League match detected: {home} vs {away} at {datetime.utcfromtimestamp(start_ts)} UTC")
                subprocess.run(["python", "goal_no_pl.py"])
                break
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(check_pl_games())
