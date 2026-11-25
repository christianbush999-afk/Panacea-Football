
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

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# football-data.org competition code -> football-data.co.uk code
# Scottish Premiership is excluded until a compatible provider
# is configured.
COMPETITIONS = {
    "PL": "E0",
    "PD": "SP1",
    "SA": "I1",
    "BL1": "D1",
    "FL1": "F1",
    "DED": "N1",
}

ALIASES = {
    "Manchester United": "Man United",
    "Manchester United FC": "Man United",
    "Manchester City": "Man City",
    "Manchester City FC": "Man City",
    "Tottenham Hotspur": "Tottenham",
    "Tottenham Hotspur FC": "Tottenham",
    "Newcastle United": "Newcastle",
    "Newcastle United FC": "Newcastle",
    "Wolverhampton Wanderers": "Wolves",
    "Wolverhampton Wanderers FC": "Wolves",
    "Nottingham Forest": "Nott'm Forest",
    "Nottingham Forest FC": "Nott'm Forest",
    "Brighton": "Brighton",
    "Brighton & Hove Albion": "Brighton",
    "Brighton & Hove Albion FC": "Brighton",
    "West Ham United": "West Ham",
    "West Ham United FC": "West Ham",
    "Manchester United FC": "Man United",
    "Liverpool FC": "Liverpool",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Brentford FC": "Brentford",
    "Aston Villa FC": "Aston Villa",
    "Crystal Palace FC": "Crystal Palace",
    "Leicester City FC": "Leicester",
    "Southampton FC": "Southampton",
    "Ipswich Town FC": "Ipswich",
    "AFC Bournemouth": "Bournemouth",
    "Atlético Madrid": "Ath Madrid",
    "Atletico Madrid": "Ath Madrid",
    "Club Atlético de Madrid": "Ath Madrid",
    "Athletic Club": "Ath Bilbao",
    "Athletic Club de Bilbao": "Ath Bilbao",
    "Real Madrid CF": "Real Madrid",
    "FC Barcelona": "Barcelona",
    "Real Betis": "Betis",
    "Real Betis Balompié": "Betis",
    "Real Sociedad": "Sociedad",
    "Real Sociedad de Fútbol": "Sociedad",
    "Inter": "Inter",
    "FC Internazionale Milano": "Inter",
    "AC Milan": "Milan",
    "AS Roma": "Roma",
    "Bayern München": "Bayern Munich",
    "FC Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Dortmund",
    "Bayer Leverkusen": "Leverkusen",
    "Bayer 04 Leverkusen": "Leverkusen",
    "Paris Saint Germain": "Paris SG",
    "Paris Saint-Germain": "Paris SG",
    "Paris Saint-Germain FC": "Paris SG",
    "PSV Eindhoven": "PSV",
}


def history():
    """Download historical football results."""

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
                    on_bad_lines="skip",
                )

                needed = [
                    "Div",
                    "Date",
                    "HomeTeam",
                    "AwayTeam",
                    "FTHG",
                    "FTAG",
                    "FTR",
                ]

                if not set(needed).issubset(frame.columns):
                    continue

                frame = frame[needed].copy()

                frame["Date"] = pd.to_datetime(
                    frame["Date"],
                    dayfirst=True,
                    errors="coerce",
                )

                for col in ("FTHG", "FTAG"):
                    frame[col] = pd.to_numeric(
                        frame[col],
                        errors="coerce",
                    )

                frames.append(
                    frame.dropna(
                        subset=[
                            "Date",
                            "FTHG",
                            "FTAG",
                            "HomeTeam",
                            "AwayTeam",
                        ]
                    )
                )

            except Exception as exc:
                print(
                    "History unavailable:",
                    code,
                    season,
                    str(exc)[:120],
                )

    if not frames:
        return pd.DataFrame(
            columns=[
                "Div",
                "Date",
                "HomeTeam",
                "AwayTeam",
                "FTHG",
                "FTAG",
                "FTR",
            ]
        )

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(
            subset=[
                "Div",
                "Date",
                "HomeTeam",
                "AwayTeam",
            ]
        )
        .sort_values("Date")
    )


def _football_data_request(competition):
    """Fetch scheduled fixtures for one competition."""

    key = os.environ.get(
        "FOOTBALL_DATA_TOKEN", ""
    ).strip()

    if not key:
        raise RuntimeError(
            "FOOTBALL_DATA_TOKEN missing from "
            "GitHub Actions environment"
        )

    url = (
        f"{FOOTBALL_DATA_BASE}/competitions/"
        f"{competition}/matches"
    )

    response = requests.get(
        url,
        params={"status": "SCHEDULED"},
        headers={"X-Auth-Token": key},
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def _normalise_team(name):
    """Convert provider team names to historical names."""

    if not name:
        return ""

    return ALIASES.get(name, name)


def fixtures():
    """Fetch upcoming fixtures for the next 24 hours."""

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=24)

    cols = [
        "fixture_id",
        "kickoff",
        "league",
        "home",
        "away",
    ]

    rows = []

    diagnostics = {
        "provider": "football-data.org",
        "window_hours": 24,
        "league_results": {},
        "errors": {},
        "raw_matches": 0,
        "accepted": 0,
        "outside_window": 0,
        "not_scheduled": 0,
        "invalid_kickoff": 0,
    }

    for competition, league_code in COMPETITIONS.items():
        try:
            payload = _football_data_request(
                competition
            )

        except requests.RequestException as exc:
            diagnostics["errors"][
                league_code
            ] = str(exc)[:200]

            diagnostics["league_results"][
                league_code
            ] = 0

            continue

        except ValueError as exc:
            diagnostics["errors"][
                league_code
            ] = str(exc)[:200]

            diagnostics["league_results"][
                league_code
            ] = 0

            continue

        items = payload.get("matches", [])

        diagnostics["league_results"][
            league_code
        ] = len(items)

        diagnostics["raw_matches"] += len(items)

        for item in items:
            status = item.get("status")

            if status not in (
                "SCHEDULED",
                "TIMED",
            ):
                diagnostics["not_scheduled"] += 1
                continue

            kickoff = pd.to_datetime(
                item.get("utcDate"),
                utc=True,
                errors="coerce",
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

            home_team = item.get(
                "homeTeam"
            ) or {}

            away_team = item.get(
                "awayTeam"
            ) or {}

            home = _normalise_team(
                home_team.get("name", "")
            )

            away = _normalise_team(
                away_team.get("name", "")
            )

            if not home or not away:
                continue

            fixture_id = item.get("id")

            if fixture_id is None:
                continue

            rows.append({
                "fixture_id": str(fixture_id),
                "kickoff": kickoff.isoformat(),
                "league": league_code,
                "home": home,
                "away": away,
            })

            diagnostics["accepted"] += 1

    frame = pd.DataFrame(
        rows,
        columns=cols,
    ).drop_duplicates(
        subset=["fixture_id"]
    )

    frame.to_csv(
        DATA / "fixtures.csv",
        index=False,
    )

    diagnostics["qualifying_fixtures"] = len(frame)

    diagnostics["checked_at"] = now.isoformat()

    (
        DATA / "fixture_diagnostics.json"
    ).write_text(
        json.dumps(diagnostics, indent=2)
    )

    print("Fixture diagnostics:")
    print(json.dumps(diagnostics, indent=2))

    if diagnostics["errors"]:
        print(
            "WARNING: Some competitions failed. "
            "Check football-data.org plan coverage."
        )

    if frame.empty:
        print(
            "No qualifying fixtures found "
            "in the next 24 hours."
        )

    return frame


def odds():
    """Read authorised bookmaker quotes only."""

    path = DATA / "odds.csv"

    cols = [
        "fixture_id",
        "market",
        "decimal_odds",
        "bookmaker",
    ]

    if not path.exists():
        return pd.DataFrame(columns=cols)

    frame = pd.read_csv(
        path,
        dtype={"fixture_id": str},
    )

    if not set(cols).issubset(frame.columns):
        raise ValueError(
            "odds.csv missing required columns"
        )

    frame = frame[cols].copy()

    frame["decimal_odds"] = pd.to_numeric(
        frame["decimal_odds"],
        errors="coerce",
    )

    return frame[
        frame["decimal_odds"] > 1
    ]
