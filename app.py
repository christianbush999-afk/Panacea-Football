
from pathlib import Path
import json

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='Panacea Football Value Scanner',
    page_icon='⚽',
    layout='wide'
)

st.title('⚽ Panacea Football Value Scanner')
st.caption(
    'Football probability research | '
    'Next 72 hours | No automatic betting'
)

root = Path(__file__).parent / 'data'
state_path = root / 'scan_state.json'

if state_path.exists():
    info = json.loads(state_path.read_text())

    st.caption(
        'Last run (UTC): ' + info.get('run_utc', 'Unknown')
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        'Fixtures',
        info.get('fixtures_next_72h', 0)
    )
    c2.metric(
        'Modelled matches',
        info.get('modelled_fixtures', 0)
    )
    c3.metric(
        'Value candidates',
        info.get('value_candidates', 0)
    )

    st.metric('Odds quotes', info.get('odds_rows', 0))

    with st.expander('Scan diagnostics'):
        st.write(
            'Historical matches:',
            info.get('historical_matches', 0)
        )
        st.write(
            'Fixtures without a model:',
            info.get('unmodelled_fixtures', 0)
        )
        st.json(info.get('fixture_diagnostics', {}))

else:
    st.info('No completed scan yet.')

results_path = root / 'latest_results.csv'

st.subheader('Upcoming match probabilities')

if results_path.exists():
    try:
        df = pd.read_csv(results_path)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame()

    if not df.empty:
        league = st.selectbox(
            'League',
            ['All'] + sorted(df['league'].unique().tolist())
        )

        market = st.selectbox(
            'Market',
            ['All'] + sorted(df['market'].unique().tolist())
        )

        only_value = st.checkbox(
            'Show only value candidates',
            value=False
        )

        if league != 'All':
            df = df[df['league'] == league]

        if market != 'All':
            df = df[df['market'] == market]

        if only_value:
            df = df[df['value_candidate'] == True]

        if not df.empty:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                'Download results',
                df.to_csv(index=False),
                'panacea_football.csv'
            )
        else:
            st.info('No matches meet these filters.')

    else:
        st.info(
            'No modelled fixtures available. '
            'Check scan diagnostics.'
        )

st.subheader('Historical walk-forward model check')

back_path = root / 'backtest.csv'

if back_path.exists():
    try:
        back = pd.read_csv(back_path)
    except pd.errors.EmptyDataError:
        back = pd.DataFrame()

    if not back.empty:
        st.metric(
            'Mean 1X2 Brier score (lower is better)',
            f"{back['brier_1x2'].mean():.3f}"
        )

        st.dataframe(
            back.tail(30),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info('Not enough historical matches.')

st.warning(
    'Model probabilities are estimates, not guarantees. '
    'Value candidates require genuine bookmaker odds. '
    'Profitability has not been established by backtesting.'
)
