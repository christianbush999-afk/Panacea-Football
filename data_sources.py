
import io
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from scanner import LEAGUES

DATA = Path('data')
DATA.mkdir(exist_ok=True)

SEASONS = ['2526', '2627']

API_BASE = 'https://v3.football.api-sports.io'

API_LEAGUES = {
    39: 'E0',
    140: 'SP1',
    135: 'I1',
    78: 'D1',
    61: 'F1',
    179: 'SC0',
    88: 'N1',
}

ALIASES = {
    'Manchester United': 'Man United',
    'Manchester City': 'Man City',
    'Tottenham Hotspur': 'Tottenham',
    'Newcastle United': 'Newcastle',
    'Wolverhampton Wanderers': 'Wolves',
    'Nottingham Forest': "Nott'm Forest",
    'Brighton': 'Brighton',
    'Brighton & Hove Albion': 'Brighton',
    'West Ham United': 'West Ham',
    'Atletico Madrid': 'Ath Madrid',
    'Athletic Club': 'Ath Bilbao',
    'Real Betis': 'Betis',
    'Real Sociedad': 'Sociedad',
    'Inter': 'Inter',
    'AC Milan': 'Milan',
    'AS Roma': 'Roma',
    'Bayern München': 'Bayern Munich',
    'Borussia Dortmund': 'Dortmund',
    'Bayer Leverkusen': 'Leverkusen',
    'Paris Saint Germain': 'Paris SG',
    'Paris Saint-Germain': 'Paris SG',
    'PSV Eindhoven': 'PSV',
}


def history():
    frames = []

    for season in SEASONS:
        for code in LEAGUES:
            url = (
                'https://www.football-data.co.uk/'
                f'mmz4281/{season}/{code}.csv'
            )

            try:
                response = requests.get(url, timeout=18)
                response.raise_for_status()

                frame = pd.read_csv(
                    io.BytesIO(response.content),
                    on_bad_lines='skip'
                )

                needed = [
                    'Div', 'Date', 'HomeTeam',
                    'AwayTeam', 'FTHG', 'FTAG', 'FTR'
                ]

                if not set(needed).issubset(frame.columns):
                    continue

                frame = frame[needed].copy()

                frame['Date'] = pd.to_datetime(
                    frame['Date'],
                    dayfirst=True,
                    errors='coerce'
                )

                for col in ('FTHG', 'FTAG'):
                    frame[col] = pd.to_numeric(
                        frame[col],
                        errors='coerce'
                    )

                frames.append(
                    frame.dropna(
                        subset=[
                            'Date', 'FTHG', 'FTAG',
                            'HomeTeam', 'AwayTeam'
                        ]
                    )
                )

            except Exception as exc:
                print(
                    'History unavailable:',
                    code,
                    season,
                    str(exc)[:120]
                )

    if not frames:
        return pd.DataFrame(
            columns=[
                'Div', 'Date', 'HomeTeam',
                'AwayTeam', 'FTHG', 'FTAG', 'FTR'
            ]
        )

    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(
            subset=[
                'Div', 'Date',
                'HomeTeam', 'AwayTeam'
            ]
        )
        .sort_values('Date')
    )


def _api_fixtures_for_day(day):
    key = os.environ.get(
        'API_FOOTBALL_KEY', ''
    ).strip()

    if not key:
        raise RuntimeError(
            'API_FOOTBALL_KEY missing from '
            'GitHub Actions environment'
        )

    response = requests.get(
        API_BASE + '/fixtures',
        params={
            'date': day,
            'timezone': 'UTC'
        },
        headers={
            'x-apisports-key': key
        },
        timeout=30
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get('errors'):
        raise RuntimeError(
            'API-Football error: '
            + str(payload['errors'])[:300]
        )

    return payload.get('response', [])


def fixtures():
    """Fetch fixtures in the next rolling 72 hours."""

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=72)

    days = [
        (now.date() + timedelta(days=i)).isoformat()
        for i in range(
            (end.date() - now.date()).days + 1
        )
    ]

    cols = [
        'fixture_id',
        'kickoff',
        'league',
        'home',
        'away'
    ]

    rows = []
    raw_count = 0

    diagnostics = {
        'other_league': 0,
        'not_scheduled': 0,
        'outside_window': 0,
        'invalid_kickoff': 0,
        'accepted': 0
    }

    for day in days:
        items = _api_fixtures_for_day(day)
        raw_count += len(items)

        for item in items:
            league_id = item.get(
                'league', {}
            ).get('id')

            if league_id not in API_LEAGUES:
                diagnostics['other_league'] += 1
                continue

            fixture = item.get('fixture', {})

            status = fixture.get(
                'status', {}
            ).get('short')

            if status != 'NS':
                diagnostics['not_scheduled'] += 1
                continue

            kickoff = pd.to_datetime(
                fixture.get('date'),
                utc=True,
                errors='coerce'
            )

            if pd.isna(kickoff):
                diagnostics['invalid_kickoff'] += 1
                continue

            if not (
                pd.Timestamp(now)
                <= kickoff
                < pd.Timestamp(end)
            ):
                diagnostics['outside_window'] += 1
                continue

            teams = item.get('teams', {})

            home = teams.get(
                'home', {}
            ).get('name', '')

            away = teams.get(
                'away', {}
            ).get('name', '')

            rows.append({
                'fixture_id': str(
                    fixture.get('id')
                ),
                'kickoff': kickoff.isoformat(),
                'league': API_LEAGUES[league_id],
                'home': ALIASES.get(home, home),
                'away': ALIASES.get(away, away)
            })

            diagnostics['accepted'] += 1

    frame = pd.DataFrame(
        rows,
        columns=cols
    ).drop_duplicates(
        subset=['fixture_id']
    )

    frame.to_csv(
        DATA / 'fixtures.csv',
        index=False
    )

    report = {
        'raw_matches': raw_count,
        'days': days,
        'window_hours': 72,
        'filters': diagnostics,
        'qualifying_fixtures': len(frame)
    }

    (
        DATA / 'fixture_diagnostics.json'
    ).write_text(
        json.dumps(report, indent=2)
    )

    print('Fixture diagnostics:')
    print(json.dumps(report, indent=2))

    if raw_count == 0:
        print(
            'WARNING: No fixtures returned; '
            'check API plan coverage.'
        )

    return frame


def odds():
    """Read authorised bookmaker quotes only."""

    path = DATA / 'odds.csv'

    cols = [
        'fixture_id',
        'market',
        'decimal_odds',
        'bookmaker'
    ]

    if not path.exists():
        return pd.DataFrame(columns=cols)

    frame = pd.read_csv(
        path,
        dtype={'fixture_id': str}
    )

    if not set(cols).issubset(frame.columns):
        raise ValueError(
            'odds.csv missing required columns'
        )

    frame = frame[cols].copy()

    frame['decimal_odds'] = pd.to_numeric(
        frame['decimal_odds'],
        errors='coerce'
    )

    return frame[
        frame['decimal_odds'] > 1
    ]
