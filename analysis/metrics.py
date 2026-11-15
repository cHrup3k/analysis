import numpy as np
import pandas as pd
from .evaluation import included

def summarize(df, apply_exclusions=True):
    excluded=0
    if apply_exclusions and "recording" in df:
        evaluated=included(df); excluded=len(df)-len(evaluated); df=evaluated
    rows=[]
    for method in ['das','srp','srp_neighbor']:
        e=df[method+'_error_deg'].dropna().to_numpy(); ambiguous=df.get(method+'_ambiguous',pd.Series(False,index=df.index)).fillna(False)
        rows.append(dict(method=method,mae=np.mean(abs(e)) if len(e) else np.nan,rmse=np.sqrt(np.mean(e**2)) if len(e) else np.nan,
            median_absolute_error=np.median(abs(e)) if len(e) else np.nan,p90_absolute_error=np.percentile(abs(e),90) if len(e) else np.nan,
            analyzed=len(e),excluded=excluded,ambiguous=int(ambiguous.sum()),temporally_unstable=int((df.get(method+'_stability_std_deg',pd.Series(0,index=df.index))>10).sum()),rejected=int(df[method+'_angle_deg'].isna().sum())))
    return pd.DataFrame(rows)
