import io, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import requests
from scanner import LEAGUES

DATA=Path('data'); DATA.mkdir(exist_ok=True)
# football-data.co.uk: historical CSVs, check provider licence before redistribution.
SEASONS=['2526','2627']

def history():
    frames=[]
    for season in SEASONS:
        for code in LEAGUES:
            url=f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv'
            try:
                r=requests.get(url,timeout=18); r.raise_for_status()
                d=pd.read_csv(io.BytesIO(r.content),on_bad_lines='skip')
                needed={'Div','Date','HomeTeam','AwayTeam','FTHG','FTAG','FTR'}
                if not needed.issubset(d.columns): continue
                d=d[list(needed)].copy()
                d['Date']=pd.to_datetime(d['Date'],dayfirst=True,errors='coerce')
                for c in ['FTHG','FTAG']: d[c]=pd.to_numeric(d[c],errors='coerce')
                frames.append(d.dropna(subset=['Date','FTHG','FTAG','HomeTeam','AwayTeam']))
            except Exception as e: print('History unavailable:',code,season,str(e)[:120])
    if not frames: return pd.DataFrame(columns=['Div','Date','HomeTeam','AwayTeam','FTHG','FTAG','FTR'])
    return pd.concat(frames,ignore_index=True).drop_duplicates(subset=['Div','Date','HomeTeam','AwayTeam']).sort_values('Date')

def fixtures():
    """Use licensed provider fixture export; no fake fixtures. UTC timestamps."""
    path=DATA/'fixtures.csv'
    cols=['fixture_id','kickoff','league','home','away']
    if not path.exists(): return pd.DataFrame(columns=cols)
    d=pd.read_csv(path,dtype={'fixture_id':str,'league':str})
    if not set(cols).issubset(d.columns): raise ValueError('fixtures.csv missing required columns')
    d=d[cols].copy(); d['kickoff']=pd.to_datetime(d['kickoff'],utc=True,errors='coerce')
    now=datetime.now(timezone.utc)
    return d[(d['kickoff']>=now)&(d['kickoff']<now+timedelta(hours=24))&d['league'].isin(LEAGUES)].copy()

def odds():
    """Only authorised/contractually permitted bookmaker odds export."""
    path=DATA/'odds.csv'
    cols=['fixture_id','market','decimal_odds','bookmaker']
    if not path.exists(): return pd.DataFrame(columns=cols)
    d=pd.read_csv(path,dtype={'fixture_id':str})
    if not set(cols).issubset(d.columns): raise ValueError('odds.csv missing required columns')
    d=d[cols].copy();d['decimal_odds']=pd.to_numeric(d['decimal_odds'],errors='coerce')
    return d[d['decimal_odds']>1]
