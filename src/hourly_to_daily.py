"""Convert reconciled official hourly PM2.5 into Belgian daily averages.
Run from the project root: python src/hourly_to_daily.py
Requires data/pm25_hourly_reconciled.csv.gz (bundled; regenerate with python src/e1a_to_hourly.py).
Writes data/pm25_daily_rebuilt.csv so the bundled modelling file is never overwritten;
the notebook compares the two files when the rebuilt one is present.
Input includes explicit UTC interval-start timestamps and official quality flags.
"""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent.parent  # project root (script lives in src/)
parts=[];stations=[]
columns=['series_id','station','official_station_code','interval_start_utc','official_pm25','verification','validity']
for chunk in pd.read_csv(ROOT/'data/pm25_hourly_reconciled.csv.gz',usecols=columns,chunksize=100000):
    timestamps=pd.to_datetime(chunk.interval_start_utc,utc=True)
    chunk['local_date']=timestamps.dt.tz_convert('Europe/Brussels').dt.strftime('%Y-%m-%d')
    accepted=chunk.verification.eq(1)&chunk.validity.isin([1,2,3])&np.isfinite(chunk.official_pm25)&chunk.official_pm25.ge(0)
    chunk['clean']=chunk.official_pm25.where(accepted)
    stations.append(chunk[['series_id','station','official_station_code']].drop_duplicates())
    parts.append(chunk.groupby(['series_id','local_date']).clean.agg(['sum','count']).reset_index())
# Combine chunks before taking means: never average chunk means.
agg=pd.concat(parts).groupby(['series_id','local_date'])[['sum','count']].sum()
metadata=pd.concat(stations).drop_duplicates('series_id').set_index('series_id')
dates=pd.date_range('2022-01-01','2025-12-31',freq='D')
index=pd.MultiIndex.from_product([metadata.index,dates.strftime('%Y-%m-%d')],names=['series_id','local_date'])
daily=agg.reindex(index,fill_value=0).reset_index()
midnight=dates.tz_localize('Europe/Brussels').tz_convert('UTC')
next_midnight=(dates+pd.Timedelta(days=1)).tz_localize('Europe/Brussels').tz_convert('UTC')
expected=pd.Series((next_midnight-midnight).total_seconds()/3600,index=dates.strftime('%Y-%m-%d'))
daily['expected_hours']=daily.local_date.map(expected).astype(int)
daily['valid_hours']=daily['count'].astype(int)
assert (daily.valid_hours<=daily.expected_hours).all()
daily['mean_available_valid_hours']=daily['sum']/daily['count'].replace(0,np.nan)
daily['minimum_valid_hours']=np.ceil(.75*daily.expected_hours).astype(int)
daily['eligible']=daily.valid_hours.ge(daily.minimum_valid_hours)
daily['coverage_pct']=100*daily.valid_hours/daily.expected_hours
daily['daily_pm25_ug_m3']=daily.mean_available_valid_hours.where(daily.eligible)
daily['above_15']=(daily.daily_pm25_ug_m3>15).astype('Int64').where(daily.eligible)
for c in ['station','official_station_code']:daily[c]=daily.series_id.map(metadata[c])
daily['year']=daily.local_date.str[:4].astype(int)
daily['split']=daily.year.map({2022:'train',2023:'train',2024:'validation',2025:'test'})
coverage=daily.groupby(['series_id','year'])[['valid_hours','expected_hours']].sum()
coverage=(100*coverage.valid_hours/coverage.expected_hours).unstack()
panel=coverage.index[(coverage[2022]>=90)&(coverage[2023]>=90)]
daily=daily[daily.series_id.isin(panel)].drop(columns=['sum','count']).sort_values(['series_id','local_date'])
assert daily.loc[~daily.eligible,['daily_pm25_ug_m3','above_15']].isna().all().all()
output=ROOT/'data'/'pm25_daily_rebuilt.csv';daily.to_csv(output,index=False)
print('Saved',output,'| stations:',len(panel),'| days:',len(daily))
print(daily.groupby('year').agg(eligible_days=('eligible','sum'),elevated_days=('above_15','sum')))
