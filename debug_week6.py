#!/usr/bin/env python3

import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("CFBD_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(
    "https://api.collegefootballdata.com/games",
    headers=headers,
    params={"year": 2025, "week": 6, "division": "fbs"},
)

if response.status_code == 200:
    games = response.json()
    problem_games = []
    complete_games = 0
    incomplete_games = 0

    for game in games:
        if game.get("completed") is True:
            if game.get("home_points") is None or game.get("away_points") is None:
                problem_games.append(
                    {
                        "id": game.get("id"),
                        "away": game.get("away_team"),
                        "home": game.get("home_team"),
                        "home_points": game.get("home_points"),
                        "away_points": game.get("away_points"),
                    }
                )
            else:
                complete_games += 1
        else:
            incomplete_games += 1

    print(f"Total games: {len(games)}")
    print(f"Complete games with scores: {complete_games}")
    print(f"Incomplete games: {incomplete_games}")
    print(f"Complete games missing scores: {len(problem_games)}")

    if problem_games:
        print("\nProblem games:")
        for game in problem_games:
            away = game["away"] or "Unknown"
            home = game["home"] or "Unknown"
            print(
                f"  {away} @ {home} (ID: {game['id']}): {game['away_points']} - {game['home_points']}"
            )
else:
    print(f"API Error: {response.status_code}")
