import asyncio
import tweepy
from sofascore_wrapper.api import SofascoreAPI
import aiohttp
import sys
sys.stdout.reconfigure(line_buffering=True)
import time



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
pl_matches = []

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


async def post_lineup_or_start(api, match):
    match_id = match["id"]
    if match_id in posted_lineups:
        return

    home_team = match.get("homeTeam", {}).get("shortName", "Home Team")
    away_team = match.get("awayTeam", {}).get("shortName", "Away Team")
    home_code = match.get("homeTeam", {}).get("nameCode", "")
    away_code = match.get("awayTeam", {}).get("nameCode", "")
    tournament_name = match.get("tournament", {}).get("name", "")

    posted_lineups.add(match_id)
    try:
        lineup_data = await api._get(f"/event/{match_id}/lineups")
        if lineup_data.get("confirmed") and "home" in lineup_data and "away" in lineup_data:
            home_players = [p["player"]["shortName"] for p in lineup_data["home"].get("players", []) if not p.get("substitute")]
            away_players = [p["player"]["shortName"] for p in lineup_data["away"].get("players", []) if not p.get("substitute")]

            lineup_text = (
                f"📋 Starting Lineups\n"
                f"{home_team} ({home_code}):\n" + ", ".join(home_players) + "\n\n"
                f"{away_team} ({away_code}):\n" + ", ".join(away_players) + "\n\n"
                f"{format_hashtags(home_code, away_code, tournament_name)}"
            )
            post(lineup_text)
        else:
            post(f"🏟 The game begins!\n{format_hashtags(home_code, away_code, tournament_name)}")
    except Exception:
        post(f"🏟 The game begins!\n{format_hashtags(home_code, away_code, tournament_name)}")


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
        if not inc_id or inc_id in seen_incidents:
            continue
        seen_incidents.add(inc_id)

        minute = inc.get("time", {}).get("minute") if isinstance(inc.get("time"), dict) else inc.get("time")
        if minute is None:
            minute = inc.get("minute", "?")

        incident_type = inc.get("incidentType")
        scorer = clean_name(inc.get("playerName") or inc.get("player", {}).get("shortName", ""))
        assist = clean_name(inc.get("assist1", {}).get("shortName") if "assist1" in inc else "")

        score = f'{home_team} {inc.get("homeScore")}-{inc.get("awayScore")} {away_team} ({minute}")'
        hashtags = format_hashtags(home_code, away_code, tournament_name)

        if incident_type == "goal":
            text = f"⚽️ GOAL: {scorer}" if scorer else "⚽️ GOAL:-"
            if assist:
                text += f"\n🅰️ Assist: {assist}"
            else:
                text += f"\n🅰️ Assist:-"
            text += f"\n{score}\n{hashtags}"
            post(text)

        elif incident_type == "penalty":
            text = f"✅ PENALTY GOAL: {scorer}" if scorer else "✅ PENALTY GOAL!"
            text += f"\n{score}\n{hashtags}"
            post(text)

        elif incident_type == "inGamePenalty" and inc.get("incidentClass") == "missed":
            text = f"❌ PENALTY MISSED: {scorer}" if scorer else "❌ PENALTY MISSED!"
            text += f"\n{score}\n{hashtags}"
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
        fpl_matches = [m for m in fpl_matches if m["id"] != match_id]


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


async def main():
    api = SofascoreAPI()
    print("Starting Premier League live match tracker...")
    runtime_minutes = 150  # 2.5 hours
    start_time = time.time()

    try:
        
        while True:
            # Stop the loop if runtime exceeded
            if (time.time() - start_time) > runtime_minutes * 60:
                print("Time limit reached. Stopping tracker...")
                break

            matches = await get_live_matches(api)

            if matches:
                new_pl_matches = [m for m in matches if m["homeTeam"]["name"] in PREMIER_LEAGUE_TEAMS or m["awayTeam"]["name"] in PREMIER_LEAGUE_TEAMS]
                #new_pl_matches=matches[:3]
                existing_ids = {m["id"] for m in pl_matches}

                pl_matches.extend(m for m in new_pl_matches if m["id"] not in existing_ids)

                if pl_matches:
                    for match in pl_matches:
                        if match["id"] not in posted_lineups:
                            await post_lineup_or_start(api, match)
                        await check_incidents(api, match)
                        await check_half_time(api, match)
                        await check_full_time(api, match)
                else:
                    print("No live Premier League matches right now.")
            else:
                print("No live matches at the moment.")
            await asyncio.sleep(15)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
