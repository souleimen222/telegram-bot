import asyncio
import tweepy
from sofascore_wrapper.api import SofascoreAPI
import aiohttp
import sys
sys.stdout.reconfigure(line_buffering=True)
import time
from datetime import datetime, timezone




# ==== CONFIG ====
PREMIER_LEAGUE_TEAMS = {
    "Manchester City", "Manchester United", "Liverpool", "Arsenal",
    "Chelsea", "Tottenham Hotspur", "Newcastle United", "Aston Villa",
    "Brighton & Hove Albion", "West Ham United", "Wolverhampton Wanderers",
    "Crystal Palace", "Fulham", "Brentford", "Everton", "Nottingham Forest",
    "Bournemouth", "Sunderland", "Leeds United", "Burnley"
}

# Twitter API credentials
TWITTER_API_KEY = "YOUR_KEY"
TWITTER_API_SECRET = "YOUR_SECRET"
TWITTER_ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
TWITTER_ACCESS_SECRET = "YOUR_ACCESS_SECRET"

# Telegram Bot credentials
TELEGRAM_BOT_TOKEN = "8367254953:AAESxN8LQFNDkjFxUIRUJ5vxoP-dU5sjqe4"
TELEGRAM_CHAT_ID = "@FPL_EDITS"

# Setup Twitter client
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
twitter_api = tweepy.API(auth)

# Track seen incidents to avoid duplicate tweets/posts
seen_incidents = set()
posted_lineups = set()
posted_results = set()  # FT posted matches
posted_half_times = set()  # HT posted matches
old_pl_ids=[]

async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload) as resp:
            if resp.status != 200:
                print(f"Telegram error: {await resp.text()}")


def post(text):
    print(text)  # Debug
    asyncio.create_task(send_telegram_message(text))


def tweet_update(text):
    try:
        twitter_api.update_status(text)
        print(f"Tweeted: {text}")
    except Exception as e:
        print(f"Twitter error: {e}")


def format_hashtags(home_code, away_code, competition_name):
    comp_tag = competition_name.replace("-", " ").title().replace(" ", "")
    comp_tag = competition_name.replace(",", "_").title().replace(" ", "")
    return f"#{home_code}{away_code} #{comp_tag}"


def clean_name(name):
    if not name or name.strip() in ["-", "Unknown"]:
        return ""
    return name.strip()


async def get_live_matches(api):
    data = await api._get("/sport/football/events/live")
    return data.get("events", [])

async def get_today_matches(api):
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = await api._get(f"/sport/football/scheduled-events/{date_str}")
    return data.get("events", [])


async def post_lineup(api, match):
    match_id = match["id"]
    if match_id in posted_lineups:
        return

    home_team = match.get("homeTeam", {}).get("shortName", "Home Team")
    away_team = match.get("awayTeam", {}).get("shortName", "Away Team")
    home_code = match.get("homeTeam", {}).get("nameCode", "")
    away_code = match.get("awayTeam", {}).get("nameCode", "")
    tournament_name = match.get("tournament", {}).get("name", "")
    status = match["status"]["description"]
    
    
    lineup_data = await api._get(f"/event/{match_id}/lineups")
    if lineup_data and "error" not in lineup_data:
        if lineup_data.get("confirmed") and "home" in lineup_data and "away" in lineup_data:
            posted_lineups.add(match_id)
            home_players = [p["player"]["shortName"] for p in lineup_data["home"].get("players", []) if not p.get("substitute")]
            away_players = [p["player"]["shortName"] for p in lineup_data["away"].get("players", []) if not p.get("substitute")]

            lineup_text = (
                f"📋 {home_team} vs {away_team} Team News : \n"
                f"{home_team} XI : " + ", ".join(home_players) + "\n\n"
                f"{away_team} XI : " + ", ".join(away_players) + "\n\n"
                f"{format_hashtags(home_code, away_code, tournament_name)}"
            )
            post(lineup_text)
            return
    if status!="Not started":
        posted_lineups.add(match_id)



async def check_incidents(api, match):
    match_id = match["id"]
    home_team = match.get("homeTeam", {}).get("shortName", "Home Team")
    away_team = match.get("awayTeam", {}).get("shortName", "Away Team")
    home_code = match.get("homeTeam", {}).get("nameCode", "")
    away_code = match.get("awayTeam", {}).get("nameCode", "")
    tournament_name = match.get("tournament", {}).get("name", "")

    data = await api._get(f"/event/{match_id}/incidents")
    incidents = data.get("incidents", [])

    for inc in incidents:
        inc_id = inc.get("id")
        incident_type = inc.get("incidentType")

        if not inc_id or inc_id in seen_incidents:
            continue

        if incident_type == "goal" or incident_type == "penalty" :
            await asyncio.sleep(15)

            data = await api._get(f"/event/{match_id}/incidents")
            updated_inc = next((i for i in data.get("incidents", []) if i.get("id") == inc_id), None)
            if not updated_inc:
                continue
        else:
            updated_inc=inc

        seen_incidents.add(inc_id)
        minute = updated_inc.get("time", {}).get("minute") if isinstance(updated_inc.get("time"), dict) else updated_inc.get("time")
        if minute is None:
            minute = updated_inc.get("minute", "?")

        incident_type = updated_inc.get("incidentType")
        scorer = clean_name(updated_inc.get("playerName") or updated_inc.get("player", {}).get("shortName", ""))
        assist = clean_name(updated_inc.get("assist1", {}).get("shortName") if "assist1" in updated_inc else "")

        score = f'{home_team} {updated_inc.get("homeScore")}-{updated_inc.get("awayScore")} {away_team} ({minute}")'
        hashtags = format_hashtags(home_code, away_code, tournament_name)

        if incident_type == "goal":
            text = f"⚽️ GOAL: {scorer}" if scorer else "⚽️ GOAL:-"
            if assist:
                text += f"\n🅰️ Assist: {assist}"
            else:
                text += f"\n🅰️ Assist:-"
            text += f"\n\n{score}\n{hashtags}"
            post(text)

        elif incident_type == "penalty":
            text = f"✅ PENALTY GOAL: {scorer}" if scorer else "✅ PENALTY GOAL!"
            text += f"\n\n{score}\n{hashtags}"
            post(text)

        elif incident_type == "inGamePenalty" and updated_inc.get("incidentClass") == "missed":
            text = f"❌ PENALTY MISSED: {scorer}" if scorer else "❌ PENALTY MISSED!"
            text += f"\n\n{score}\n{hashtags}"
            post(text)


async def check_half_time(api, match):
    match_id = match["id"]
    if match_id in posted_half_times:
        return

    match_data = await api._get(f"/event/{match_id}")
    status = match_data["event"]["status"]["description"]

    if status == "Halftime":
        posted_half_times.add(match_id)

        home_team = match_data["event"]["homeTeam"]["shortName"]
        away_team = match_data["event"]["awayTeam"]["shortName"]
        home_code = match_data["event"]["homeTeam"]["nameCode"]
        away_code = match_data["event"]["awayTeam"]["nameCode"]
        tournament_name = match_data["event"]["tournament"]["name"]
        home_score = match_data["event"]["homeScore"]["current"]
        away_score = match_data["event"]["awayScore"]["current"]

        incidents_data = await api._get(f"/event/{match_id}/incidents")
        goals_lines = []
        for inc in incidents_data.get("incidents", []):
            if inc.get("incidentType") == "goal":
                scorer = clean_name(inc.get("player", {}).get("shortName", ""))
                assist = clean_name(inc.get("assist1", {}).get("shortName", ""))
                if scorer:
                    line = f"⚽️ {scorer}"
                    if assist:
                        line += f" | 🅰️ {assist}"
                    goals_lines.append(line)

        goals_text = "\n".join(goals_lines) if goals_lines else "No goals recorded."
        score_line = f"{home_team} {home_score}-{away_score} {away_team}"
        hashtags = format_hashtags(home_code, away_code, tournament_name)

        text = f"⏸ HT: {score_line}\n\n{goals_text}\n\n{hashtags}"
        post(text)


async def check_full_time(api, match):
    match_id = match["id"]
    if match_id in posted_results:
        return

    match_data = await api._get(f"/event/{match_id}")
    status = match_data["event"]["status"]["type"]

    if status == "finished":
        posted_results.add(match_id)

        home_team = match_data["event"]["homeTeam"]["shortName"]
        away_team = match_data["event"]["awayTeam"]["shortName"]
        home_code = match_data["event"]["homeTeam"]["nameCode"]
        away_code = match_data["event"]["awayTeam"]["nameCode"]
        tournament_name = match_data["event"]["tournament"]["name"]
        home_score = match_data["event"]["homeScore"]["current"]
        away_score = match_data["event"]["awayScore"]["current"]

        incidents_data = await api._get(f"/event/{match_id}/incidents")
        goals_lines = []
        for inc in incidents_data.get("incidents", []):
            if inc.get("incidentType") == "goal":
                scorer = clean_name(inc.get("player", {}).get("shortName", ""))
                assist = clean_name(inc.get("assist1", {}).get("shortName", ""))
                if scorer:
                    line = f"⚽️ {scorer}"
                    if assist:
                        line += f" | 🅰️ {assist}"
                    goals_lines.append(line)

        goals_text = "\n".join(goals_lines) if goals_lines else "No goals recorded."
        score_line = f"{home_team} {home_score}-{away_score} {away_team}"
        hashtags = format_hashtags(home_code, away_code, tournament_name)

        text = f"🏁 FT: {score_line}\n\n{goals_text}\n\n{hashtags}"
        post(text)

# And define handle_match like:
async def handle_match(api, match):
    await post_lineup(api, match)
    await check_incidents(api, match)
    await check_half_time(api, match)
    await check_full_time(api, match)

async def main():
    api = SofascoreAPI()
    print("Starting Premier League live match tracker...")
    runtime_minutes = 3*60+15  # 3:15 hours
    start_time = time.time()
    try:
        
        while True:
            # Stop the loop if runtime exceeded
            if (time.time() - start_time) > runtime_minutes * 60:
                print("Time limit reached. Stopping tracker...")
                break

            matches = await get_today_matches(api)

            now_ts = int(time.time())  # current Unix timestamp
            now_matches = [m for m in matches if now_ts - 3*3600 <= m.get("startTimestamp", 0) <= now_ts + 1*3600]

            if  now_matches:
                pl_matches = [m for m in now_matches if m["homeTeam"]["name"] in PREMIER_LEAGUE_TEAMS or m["awayTeam"]["name"] in PREMIER_LEAGUE_TEAMS]
                pl_matches = [m for m in pl_matches if m["tournament"]["name"] != "Premier League"]

                new_pl_ids = [match["id"] for match in pl_matches]
                if any(mid not in old_pl_ids for mid in new_pl_ids):
                    start_time = time.time()
                old_pl_ids=new_pl_ids

                if pl_matches:
                    tasks = [handle_match(api, match) for match in pl_matches]
                    await asyncio.gather(*tasks)

                else:
                    print("No  Premier League matches right now.")
            else:
                print("No live matches right now.")
            await asyncio.sleep(15)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

