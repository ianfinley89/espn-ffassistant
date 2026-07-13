"""
ESPN Fantasy Football — undocumented JSON API spike.

Goal: prove we can read a league's settings, rosters, the player pool, and
draft picks straight from ESPN's internal JSON API — no Selenium, no XPath.

It's the off-season, so there is no *live* draft to poll. That's fine: a
completed prior-season draft returns the same `mDraftDetail` shape a live one
does, so running this against last year validates auth + endpoints + parsing.
The only thing it can't exercise until draft night is the polling cadence.

Usage:
    1. Copy .env.example -> .env and fill in the values (see spike/README.md
       for how to grab the cookies from your browser).
    2. pip install requests python-dotenv
    3. python spike/espn_api_spike.py

Public leagues need only LEAGUE_ID + SEASON. Private leagues also need the
ESPN_S2 and SWID cookies.
"""

import json
import os
import sys

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # .env is optional; env vars may be set another way.


BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"


def get_config():
    league_id = os.environ.get("LEAGUE_ID")
    season = os.environ.get("SEASON")
    if not league_id or not season:
        sys.exit(
            "Missing config. Set LEAGUE_ID and SEASON (in a .env file or env "
            "vars). See spike/README.md."
        )
    cookies = {}
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("SWID")
    if espn_s2 and swid:
        cookies = {"espn_s2": espn_s2, "SWID": swid}
    return league_id, season, cookies


def fetch(league_id, season, cookies, views, extra_headers=None):
    """Hit the league endpoint with one or more `view` params."""
    url = f"{BASE}/seasons/{season}/segments/0/leagues/{league_id}"
    params = [("view", v) for v in views]
    headers = {"User-Agent": "Mozilla/5.0"}
    if extra_headers:
        headers.update(extra_headers)
    resp = requests.get(url, params=params, cookies=cookies, headers=headers, timeout=20)
    if resp.status_code == 401:
        sys.exit(
            "401 Unauthorized — this looks like a private league. Set ESPN_S2 "
            "and SWID cookies in .env. See spike/README.md."
        )
    resp.raise_for_status()
    return resp.json()


def build_player_map(league_id, season, cookies, limit=400):
    """id -> name map from the draftable player pool (kona_player_info)."""
    filt = {
        "players": {
            "limit": limit,
            "sortDraftRanks": {
                "sortPriority": 100,
                "sortAsc": True,
                "value": "STANDARD",
            },
        }
    }
    try:
        data = fetch(
            league_id,
            season,
            cookies,
            ["kona_player_info"],
            extra_headers={"x-fantasy-filter": json.dumps(filt)},
        )
    except requests.HTTPError as exc:
        print(f"  (couldn't load player pool: {exc}; picks will show IDs only)")
        return {}
    players = data.get("players", [])
    return {p["id"]: p.get("player", {}).get("fullName", f"#{p['id']}") for p in players}


def show_settings(data):
    settings = data.get("settings", {})
    print("=" * 60)
    print(f"League:   {settings.get('name', '(unknown)')}")
    size = settings.get("size")
    if size:
        print(f"Teams:    {size}")
    scoring = settings.get("scoringSettings", {})
    scoring_type = scoring.get("scoringType")
    if scoring_type:
        print(f"Scoring:  {scoring_type}")
    roster = settings.get("rosterSettings", {})
    slots = roster.get("lineupSlotCounts")
    if slots:
        # Only print the non-zero slots; slot ids map to positions.
        active = {k: v for k, v in slots.items() if v}
        print(f"Roster slots (slotId:count): {active}")
    print("=" * 60)


def show_draft(data, player_map, max_picks=20):
    detail = data.get("draftDetail", {})
    picks = detail.get("picks", [])
    print(f"\nDraft: drafted={detail.get('drafted')}, inProgress="
          f"{detail.get('inProgress')}, picks={len(picks)}")
    if not picks:
        print("  (no picks yet — expected in the off-season before draft night)")
        return
    print(f"  Showing first {min(max_picks, len(picks))} picks:")
    for pick in picks[:max_picks]:
        pid = pick.get("playerId")
        name = player_map.get(pid, f"#{pid}")
        print(
            f"    R{pick.get('roundId'):>2} "
            f"P{pick.get('roundPickNumber'):>2} "
            f"(overall {pick.get('overallPickNumber'):>3}) "
            f"team {pick.get('teamId'):>2} -> {name}"
        )


def show_teams(data, player_map, max_teams=3):
    teams = data.get("teams", [])
    print(f"\nTeams: {len(teams)} found. Sample rosters:")
    for team in teams[:max_teams]:
        name = team.get("name") or f"Team {team.get('id')}"
        entries = team.get("roster", {}).get("entries", [])
        players = [
            player_map.get(
                e.get("playerId"),
                e.get("playerPoolEntry", {}).get("player", {}).get("fullName", "?"),
            )
            for e in entries
        ]
        print(f"  {name}: {len(players)} players")
        if players:
            print(f"    {', '.join(players[:8])}{' ...' if len(players) > 8 else ''}")


def main():
    league_id, season, cookies = get_config()
    mode = "PRIVATE (cookie auth)" if cookies else "PUBLIC (no auth)"
    print(f"Querying league {league_id}, season {season} — {mode}\n")

    print("Building player id->name map from the draftable pool...")
    player_map = build_player_map(league_id, season, cookies)
    print(f"  loaded {len(player_map)} players\n")

    data = fetch(
        league_id, season, cookies, ["mSettings", "mDraftDetail", "mTeam", "mRoster"]
    )
    show_settings(data)
    show_draft(data, player_map)
    show_teams(data, player_map)
    print("\nSpike complete. If you see a league name, draft picks with real "
          "player names, and rosters above, the JSON-API approach is validated.")


if __name__ == "__main__":
    main()
