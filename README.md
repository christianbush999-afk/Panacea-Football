# Panacea Football Value Scanner — private v1

Research only. Seven top divisions: E0, SP1, I1, D1, F1, SC0, N1.

## Quick start
1. Upload all files to the private GitHub repository, preserving `.github/workflows/daily.yml` and `data/` paths.
2. Go to **Actions > Panacea Football Daily Scanner > Run workflow**.
3. In Streamlit Community Cloud deploy repository with main file `app.py` (check private-repository access on your plan).
4. Add **licensed fixture exports** to `data/fixtures.csv` with `fixture_id,kickoff,league,home,away`. Kickoff must be UTC ISO 8601. Team names must match football-data.co.uk historical names.
5. Add **authorised odds exports** to `data/odds.csv` with `fixture_id,market,decimal_odds,bookmaker`.

Supported market codes: `1`, `X`, `2`, `O2.5`, `U2.5`, `BTTS_Y`, `BTTS_N`. Decimal odds only.

A 5% value edge is defined as `estimated_probability * decimal_odds - 1 >= 0.05` (expected ROI, not 5 percentage points of probability). No bookmaker scraping, fabricated odds, automatic bets, or stakes.

Historical CSVs from football-data.co.uk are fetched for the 2025/26 and 2026/27 seasons. The first backtest measures out-of-sample Brier scores; it **does not** claim to measure profitable betting returns. For valid ROI backtesting, supply timestamped historical odds observed before kickoff, align exact market and settlement, include bookmaker margin, and evaluate chronologically. Team names, data availability, league coverage, and model calibration require verification.

Note: Current v1 is a scaffold and does **not** automatically discover live fixtures or fetch Paddy Power odds. Those require an approved provider integration. GitHub Actions scheduled workflows can run late and are not guaranteed to trigger exactly every six hours.
