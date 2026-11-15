"""Read-only verification of originals and presence/consistency of output artifacts."""
import hashlib, json, platform, importlib.metadata
from pathlib import Path
import numpy as np
import pandas as pd

def audit(root: Path):
    out=root/'analysis_results'; manifest=json.loads((out/'input_manifest.json').read_text())
    checked=0; mismatches=[]
    for record in manifest:
        for name,expected in record['sha256'].items():
            path=root/record['recording']/name
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            checked+=1
            if digest.hexdigest()!=expected:mismatches.append(str(path))
    df=pd.read_csv(out/'doa_results.csv'); baseline=pd.read_csv(out/'baseline_comparison.csv')
    missing=[]
    for rec in df.recording:
        for name in ['integrity.json','time.csv','frame_selection.csv','phase_frequency.csv','baselines.csv','frequency.csv',
                     'directional_spectra.png','baseline.png','time_and_spectrogram.png','frequency.png','phase.png']:
            if not (out/rec/name).exists():missing.append(f'{rec}/{name}')
    audit_result={'original_files_rehashed':checked,'modified_originals':mismatches,'recordings':len(df),
        'evaluation_included':int(df.get('evaluation_included',pd.Series(True,index=df.index)).sum()),
        'finite_das_results':int(np.isfinite(df.das_angle_deg).sum()),'finite_srp_results':int(np.isfinite(df.srp_angle_deg).sum()),
        'baseline_rows':len(baseline),'expected_baseline_rows':len(df)*15,'missing_artifacts':missing,
        'png_count':len(list(out.rglob('*.png'))),'passed':not mismatches and not missing and len(baseline)==len(df)*15}
    (out/'audit.json').write_text(json.dumps(audit_result,indent=2))
    versions={}
    for package in ['numpy','scipy','pandas','matplotlib','pytest']:
        try: versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package]='not visible in this runtime; see pytest_results.txt'
    versions['python']=platform.python_version();(out/'environment.json').write_text(json.dumps(versions,indent=2))
    paths=[root/'main.py',root/'config.py']+list(root.glob('doa/*.py'))+list(root.glob('pdm_processing/*.py'))+list(root.glob('analysis/*.py'))+list(root.glob('tests/*.py'))
    (out/'source_manifest.json').write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},indent=2))
    if not audit_result['passed']:raise RuntimeError('Audit failed; see audit.json')
    return audit_result

if __name__=='__main__':print(json.dumps(audit(Path('.').resolve()),indent=2))
