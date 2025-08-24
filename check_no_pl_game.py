import asyncio
from datetime import datetime, timezone
import subprocess
from sofascore_wrapper.api import SofascoreAPI

PREMIER_LEAGUE_TEAMS = {
    "Manchester City", "Manchester United", "Liverpool", "Arsenal",
    "Chelsea", "Tottenham Hotspur", "Newcastle United", "Aston Villa",
    "Brighton & Hove Albion", "West Ham United", "Wolverhampton Wanderers",
    "Crystal Palace", "Fulham", "Brentford", "Everton", "Nottingham Forest",
    "Bournemouth", "Sunderland", "Leeds United", "Burnley"
}

async def check_pl_games():
    api = SofascoreAPI()
    try:
        # Today's date in UTC
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data = await api._get(f"/sport/football/scheduled-events/{date_str}")
        events = data.get("events", [])

        now_ts = int(datetime.now(timezone.utc).timestamp())
        time_window_seconds = 75 * 60  # 1 hour 15 minutes

        for match in events:
            home = match.get("homeTeam", {}).get("name")
            away = match.get("awayTeam", {}).get("name")
            start_ts = match.get("startTimestamp")
            
            if not start_ts:
                continue

            if(home in PREMIER_LEAGUE_TEAMS or away in PREMIER_LEAGUE_TEAMS) and   abs(start_ts - now_ts) <= time_window_seconds and start_ts>=now_ts:#and (match["tournament"]["name"] != "Premier League")
                print(f"Premier League match detected: {home} vs {away} at {datetime.utcfromtimestamp(start_ts)} UTC")

                
                # Run your goal_no_pl.py script
                subprocess.run(["python", "goal_no_pl.py"])
                break  # stop after triggering once
            
    finally:
        await api.close()

if __name__ == "__main__":
    asyncio.run(check_pl_games())
