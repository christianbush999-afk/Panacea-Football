from datetime import datetime, timezone
import json
from pathlib import Path
from data_sources import history, fixtures, odds, DATA
from scanner import scan, backtest

def main():
    hist=history(); fix=fixtures(); prices=odds()
    results=scan(fix,hist,prices,min_edge=0.05)
    results.to_csv(DATA/'latest_results.csv',index=False)
    test=backtest(hist)
    test.to_csv(DATA/'backtest.csv',index=False)
    state={'run_utc':datetime.now(timezone.utc).isoformat(),'historical_matches':len(hist),'fixtures_next_24h':len(fix),'odds_rows':len(prices),'model_rows':len(results),'value_candidates':int(results['value_candidate'].sum()) if not results.empty else 0,'backtest_rows':len(test),'note':'Historical backtest measures calibration only. Betting ROI needs archived pre-match bookmaker prices.'}
    (DATA/'scan_state.json').write_text(json.dumps(state,indent=2))
    print(json.dumps(state,indent=2))
if __name__=='__main__':main()
