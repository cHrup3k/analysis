"""User-confirmed invalid acquisitions; no estimator parameters are changed."""
EXCLUSIONS = {'noise_0st_10m': 'Błędnie wykonane nagranie — potwierdzone przez użytkownika.'}

def annotate(df):
    result=df.copy()
    result['evaluation_included']=~result.recording.isin(EXCLUSIONS)
    result['evaluation_exclusion_reason']=result.recording.map(EXCLUSIONS).fillna('')
    return result

def included(df):
    return df[~df.recording.isin(EXCLUSIONS)].copy()
