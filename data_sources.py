
import io
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from scanner import LEAGUES

DATA = Path("data")
DATA.mkdir(exist_ok=True)

SEASONS = ["2526", "2627"]
API_BASE = "https://v3.football.api-sports.io"

API_LEAGUES = {
    39: "E0",
    140: "SP1",
    135: "I1",
    78: "D1",
    61: "F1",
    179: "SC0",
    88: "N1",
}

ALIASES = {
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Tottenham Hotspur": "Tottenham",
    "Newcastle United": "Newcastle",
    "Wolverhampton Wanderers": "Wolves",
    "Nottingham Forest": "Nott'm Forest",
    "Brighton": "Brighton",
    "Brighton & Hove Albion": "Brighton",
    "West Ham United": "West Ham",
    "Atletico Madrid": "Ath Madrid",
    "Athletic Club": "Ath Bilbao",
    "Real Betis": "Betis",
    "Real Sociedad": "Sociedad",
    "Inter": "Inter",
    "AC Milan": "Milan",
    "AS Roma": "Roma",
    "Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Dortmund",
    "Bayer Leverkusen": "Leverkusen",
    "Paris Saint Germain": "Paris SG",
    "Paris Saint-Germain": "Paris SG",
    "PSV Eindhoven": "PSV",
}


def history():
    frames = []

    for season in SEASONS:
        for code in LEAGUES:
            url = (
                "https://www.football-data.co.uk/"
                f"mmz4281/{season}/{code}.csv"
            )

            try:
                response = requests.get(url, timeout=18)
                response.raise_for_status()

                frame = pd.read_csv(
                    io.BytesIO(response.content),
                    on_bad_lines="skip"
                )

                needed = [
                    "Div", "Date", "HomeTeam",
                    "AwayTeam", "FTHG", "FTAG", "FTR"
                ]

                if not set(needed).issubset(frame.columns):
                    continue

                frame = frame[needed].copy()

                frame["Date"] = pd.to_datetime(
                    frame["Date"],
                    dayfirst=True,
                    errors="coerce"
                )

                for col in ("FTHG", "FTAG"):
                    frame[col] = pd.to_numeric(
                        frame[col],
                        errors="coerce"
                    )

                frames.append(
                    frame.dropna(
                        subset=[
                            "Date", "FTHG", "FTAG",
                            "HomeTeam", "AwayTeam"
                        ]
                    )
                )

            except Exception as exc:
                print(
                    "History unavailable:",
                    code, season, str(exc)[:120]
                )

    if not frames:
        return pd.DataFrame(
            columns=[
                "Div", "Date", "HomeTeam",
                "AwayTeam", "FTHG", "FTAG", "FTR"
            ]
        )

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(
            subset=[
                "Div", "Date",
                "HomeTeam", "AwayTeam"
            ]
        )
        .sort_values("Date")
    )


def _api_request(params):
    key = os.environ.get(
        "API_FOOTBALL_KEY", ""
    ).strip()

    if not key:
        raise RuntimeError(
            "API_FOOTBALL_KEY missing from "
            "GitHub Actions environment"
        )

    response = requests.get(
        API_BASE + "/fixtures",
        params=params,
        headers={"x-apisports-key": key},
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def _api_fixtures_for_day(day):
    payload = _api_request({
        "date": day,
        "timezone": "UTC"
    })

    if payload.get("errors"):
        print(
            "API date error:",
            day,
            str(payload["errors"])[:300]
        )
        return []

    return payload.get("response", [])


def fixtures():
    """Fetch upcoming fixtures for selected leagues."""

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=24)

    cols = [
        "fixture_id",
        "kickoff",
        "league",
        "home",
        "away"
    ]

    rows = []

    diagnostics = {
        "window_hours": 24,
        "league_results": {},
        "errors": {},
        "raw_matches": 0,
        "accepted": 0,
        "outside_window": 0,
        "not_scheduled": 0,
        "invalid_kickoff": 0
    }

    # Query the seven selected leagues individually.
    # Two UTC calendar dates may overlap a 24h window.
    days = sorted({
        now.date().isoformat(),
        end.date().isoformat()
    })

    for league_id, league_code in API_LEAGUES.items():
        league_total = 0

        for day in days:
            season = (
                int(day[:4])
                if int(day[5:7]) >= 7
                else int(day[:4]) - 1
            )

            params = {
                "league": league_id,
                "season": season,
                "date": day,
                "timezone": "UTC"
            }

            try:
                payload = _api_request(params)

            except requests.RequestException as exc:
                diagnostics["errors"][
                    f"{league_code}:{day}"
                ] = str(exc)[:200]
                continue

            if payload.get("errors"):
                diagnostics["errors"][
                    f"{league_code}:{day}"
                ] = str(payload["errors"])[:300]
                continue

            items = payload.get("response", [])
            league_total += len(items)
            diagnostics["raw_matches"] += len(items)

            for item in items:
                fixture = item.get("fixture", {})

                status = fixture.get(
                    "status", {}
                ).get("short")

                if status != "NS":
                    diagnostics["not_scheduled"] += 1
                    continue

                kickoff = pd.to_datetime(
                    fixture.get("date"),
                    utc=True,
                    errors="coerce"
                )

                if pd.isna(kickoff):
                    diagnostics["invalid_kickoff"] += 1
                    continue

                if not (
                    pd.Timestamp(now)
                    <= kickoff
                    < pd.Timestamp(end)
                ):
                    diagnostics["outside_window"] += 1
                    continue

                teams = item.get("teams", {})

                home = teams.get(
                    "home", {}
                ).get("name", "")

                away = teams.get(
                    "away", {}
                ).get("name", "")

                rows.append({
                    "fixture_id": str(
                        fixture.get("id")
                    ),
                    "kickoff": kickoff.isoformat(),
                    "league": league_code,
                    "home": ALIASES.get(home, home),
                    "away": ALIASES.get(away, away)
                })

                diagnostics["accepted"] += 1

        diagnostics["league_results"][
            league_code
        ] = league_total

    frame = pd.DataFrame(
        rows,
        columns=cols
    ).drop_duplicates(
        subset=["fixture_id"]
    )

    frame.to_csv(
        DATA / "fixtures.csv",
        index=False
    )

    diagnostics["qualifying_fixtures"] = len(frame)
    diagnostics["days"] = days

    (
        DATA / "fixture_diagnostics.json"
    ).write_text(
        json.dumps(diagnostics, indent=2)
    )

    print("Fixture diagnostics:")
    print(json.dumps(diagnostics, indent=2))

    if diagnostics["errors"]:
        print(
            "WARNING: Some API requests failed "
            "or were rejected. Check plan coverage."
        )

    if frame.empty:
        print(
            "No qualifying fixtures found in "
            "the next 24 hours."
        )

    return frame


def odds():
    """Read authorised bookmaker quotes only."""

    path = DATA / "odds.csv"

    cols = [
        "fixture_id",
        "market",
        "decimal_odds",
        "bookmaker"
    ]

    if not path.exists():
        return pd.DataFrame(columns=cols)

    frame = pd.read_csv(
        path,
        dtype={"fixture_id": str}
    )

    if not set(cols).issubset(frame.columns):
        raise ValueError(
            "odds.csv missing required columns"
        )

    frame = frame[cols].copy()

    frame["decimal_odds"] = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce"
    )

    return frame[
        frame["decimal_odds"] > 1
    ]
