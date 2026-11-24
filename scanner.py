"""Research-only football probability and value scanner. No wagering automation."""
import math
import numpy as np
import pandas as pd

LEAGUES = {'E0':'England Premier League','SP1':'Spain La Liga','I1':'Italy Serie A','D1':'Germany Bundesliga','F1':'France Ligue 1','SC0':'Scotland Premiership','N1':'Netherlands Eredivisie'}
MARKETS = ['1','X','2','O2.5','U2.5','BTTS_Y','BTTS_N']

def poisson(k, rate):
    return math.exp(-rate)*rate**k/math.factorial(k)

def probabilities(home_rate, away_rate):
    h=np.array([poisson(i,home_rate) for i in range(12)])
    a=np.array([poisson(i,away_rate) for i in range(12)])
    matrix=np.outer(h,a); matrix=matrix/matrix.sum()
    home=sum(matrix[i,j] for i in range(12) for j in range(12) if i>j)
    draw=sum(matrix[i,i] for i in range(12))
    under=sum(matrix[i,j] for i in range(12) for j in range(12) if i+j<=2)
    btts=sum(matrix[i,j] for i in range(1,12) for j in range(1,12))
    return {'1':home,'X':draw,'2':1-home-draw,'O2.5':1-under,'U2.5':under,'BTTS_Y':btts,'BTTS_N':1-btts}

def estimate(history, league, home, away, cutoff=None):
    df=history[history['Div']==league].copy()
    if cutoff is not None: df=df[df['Date']<cutoff]
    df=df.sort_values('Date').tail(500)
    if len(df)<50: return None
    hg=df['FTHG'].mean(); ag=df['FTAG'].mean()
    if pd.isna(hg) or pd.isna(ag) or hg<=0 or ag<=0: return None
    h=df[df['HomeTeam']==home].tail(12)
    a=df[df['AwayTeam']==away].tail(12)
    if len(h)<5 or len(a)<5: return None
    # Shrink team rates toward league baseline to reduce small-sample overfitting.
    weight=0.65
    home_attack=weight*(h['FTHG'].mean()/hg)+(1-weight)
    away_defence=weight*(a['FTHG'].mean()/hg)+(1-weight)
    away_attack=weight*(a['FTAG'].mean()/ag)+(1-weight)
    home_defence=weight*(h['FTAG'].mean()/ag)+(1-weight)
    home_rate=float(np.clip(hg*home_attack*away_defence,0.2,4.5))
    away_rate=float(np.clip(ag*away_attack*home_defence,0.2,4.5))
    return probabilities(home_rate,away_rate)

def scan(fixtures, history, odds, min_edge=0.05):
    rows=[]
    if fixtures.empty: return pd.DataFrame()
    for _, f in fixtures.iterrows():
        cutoff=pd.to_datetime(f['kickoff'],utc=True)
        probs=estimate(history,str(f['league']),str(f['home']),str(f['away']),cutoff)
        if probs is None: continue
        fixture_odds=odds[(odds['fixture_id'].astype(str)==str(f['fixture_id']))] if not odds.empty else pd.DataFrame()
        for market,p in probs.items():
            match=fixture_odds[fixture_odds['market']==market] if not fixture_odds.empty else pd.DataFrame()
            price=float(match.iloc[-1]['decimal_odds']) if not match.empty else np.nan
            provider=str(match.iloc[-1].get('bookmaker','')) if not match.empty else ''
            edge=(p*price-1) if pd.notna(price) and price>1 else np.nan
            rows.append({'fixture_id':f['fixture_id'],'kickoff':f['kickoff'],'league':LEAGUES.get(f['league'],f['league']), 'home':f['home'],'away':f['away'],'market':market,'model_probability':round(p,4),'fair_odds':round(1/p,3) if p>0 else np.nan,'bookmaker':provider,'decimal_odds':price,'expected_roi':round(edge,4) if pd.notna(edge) else np.nan,'value_candidate':bool(pd.notna(edge) and edge>=min_edge)})
    result=pd.DataFrame(rows)
    return result.sort_values(['value_candidate','expected_roi'],ascending=[False,False],na_position='last') if not result.empty else result

def backtest(history, min_edge=0.05, max_matches=250):
    """Walk-forward evaluation of match-result probabilities; no claim of profitable odds backtest."""
    df=history.sort_values('Date').reset_index(drop=True)
    records=[]
    for i in range(150,len(df)):
        f=df.iloc[i]
        prior=df.iloc[:i]
        p=estimate(prior,f['Div'],f['HomeTeam'],f['AwayTeam'],f['Date'])
        if p is None: continue
        outcome=f['FTR']
        actual={'H':'1','D':'X','A':'2'}.get(outcome)
        if actual:
            records.append({'date':str(f['Date'].date()),'league':f['Div'],'outcome':actual,'probability_of_actual':round(p[actual],4),'brier_1x2':round(sum((p[k]-int(k==actual))**2 for k in ['1','X','2'])/3,5)})
        if len(records)>=max_matches: break
    return pd.DataFrame(records)
