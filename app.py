from pathlib import Path
import json
import pandas as pd
import streamlit as st
from scanner import LEAGUES

st.set_page_config(page_title='Panacea Football Value Scanner',page_icon='⚽',layout='wide')
st.title('⚽ Panacea Football Value Scanner')
st.caption('Private research dashboard · Next 24 hours · No automatic betting')
root=Path(__file__).parent/'data'
state=root/'scan_state.json'
if state.exists():
    info=json.loads(state.read_text())
    st.caption('Last run (UTC): '+info.get('run_utc','Unknown'))
    c1,c2,c3=st.columns(3)
    c1.metric('Fixtures',info.get('fixtures_next_24h',0))
    c2.metric('Value candidates',info.get('value_candidates',0))
    c3.metric('Odds quotes',info.get('odds_rows',0))
else:st.info('No completed scan yet. Run the GitHub workflow.')
file=root/'latest_results.csv'
if file.exists():
    try: df=pd.read_csv(file)
    except pd.errors.EmptyDataError:df=pd.DataFrame()
    if not df.empty:
        league=st.selectbox('League',['All']+sorted(df.league.unique().tolist()))
        market=st.selectbox('Market',['All']+sorted(df.market.unique().tolist()))
        only=st.checkbox('Value candidates only (≥5% expected ROI)',value=True)
        if league!='All':df=df[df.league==league]
        if market!='All':df=df[df.market==market]
        if only:df=df[df.value_candidate==True]
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button('Download results',df.to_csv(index=False),'panacea_football.csv')
    else:st.info('No modelled fixtures yet. Add licensed fixture and odds CSVs.')
st.subheader('Historical walk-forward model check')
back=root/'backtest.csv'
if back.exists():
    try: b=pd.read_csv(back)
    except pd.errors.EmptyDataError:b=pd.DataFrame()
    if not b.empty:
        st.metric('Mean 1X2 Brier score (lower is better)',f"{b.brier_1x2.mean():.3f}")
        st.dataframe(b.tail(30),use_container_width=True,hide_index=True)
    else:st.info('Not enough historical matches for backtesting.')
st.warning('Estimated probabilities are uncalibrated. 5% modelled expected ROI is not a guaranteed edge. A proper betting ROI backtest requires time-stamped pre-match odds, no look-ahead, and out-of-sample validation.')
