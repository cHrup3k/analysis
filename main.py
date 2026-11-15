"""Reproducible PDM array analysis. Never uses references in spatial estimators."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/doa-matplotlib')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse, json, traceback, platform
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import signal
from config import Config, BANDS
from pdm_processing.packet_validation import inspect, pcm_valid_mask
from pdm_processing.decimation import cached_pcm, design_filter
from pdm_processing.signal_preparation import prepare
from doa.geometry import delays
from doa.pair_analysis import SpatialEngine,peak_summary
from doa.time_analysis import time_rows
from doa.phase_diagnostics import diagnose
from analysis.recording_scanner import recordings
from analysis.reference_parser import parse_reference
from analysis.metrics import summarize
from analysis.visualization import recording_plots,summary_plots
from analysis.reporting import report

def filter_characteristics(cfg,out):
    rows=[]
    for length in [1001,cfg.numtaps]:
        taps=signal.firwin(length,cfg.cutoff,fs=cfg.pdm_fs,window=('kaiser',cfg.beta))
        f,h=signal.freqz(taps,worN=262144,fs=cfg.pdm_fs); db=20*np.log10(np.maximum(abs(h),1e-20))
        rows.append(dict(numtaps=length,group_delay_pdm=(length-1)/2,group_delay_s=(length-1)/2/cfg.pdm_fs,
          passband_0_4k_max_loss_db=float(-db[f<=4000].min()),passband_0_15k_max_loss_db=float(-db[f<=15000].min()),
          stopband_from_25k_db=float(-db[f>=25000].max()),symmetry_error=float(abs(taps-taps[::-1]).max())))
    pd.DataFrame(rows).to_csv(out/'filter_characteristics.csv',index=False)
    return rows

def run(args):
    cfg=Config(); root=Path(args.root).resolve(); out=root/'analysis_results'; out.mkdir(exist_ok=True)
    (out/'plots').mkdir(exist_ok=True)
    (out/'processing_config.json').write_text(json.dumps(dict(config=cfg.dictionary(),start=args.start,stop=args.stop,
        python=platform.python_version(),numpy=np.__version__,source_clock='nominal, corroborated by ../pdm_udp.py; no per-capture clock log',
        masks='energy >=3x per-frequency temporal 20th percentile; SNR >=1% frame max; local adjacent coherence >=0.4 over 3 frames x 5 bins; common weights proportional to excess SNR',
        ambiguity='second local maximum >=5 degrees away; floor-subtracted ratio >=0.9',
        packet_size='inferred independently from exact interleaved frame count / mask length'),indent=2))
    filt=filter_characteristics(cfg,out)
    results=[]; all_base=[]; all_freq=[]; all_chan=[]; all_phase=[]; inventories=[]
    for folder in recordings(root):
        print('Processing',folder.name,flush=True)
        dest=out/folder.name; dest.mkdir(exist_ok=True)
        ref,distance=parse_reference(folder.name)
        row=dict(recording=folder.name,reference_angle_deg=ref,reference_distance_m=distance,status='failed',
          das_angle_deg=np.nan,srp_angle_deg=np.nan,srp_neighbor_angle_deg=np.nan,
          das_error_deg=np.nan,srp_error_deg=np.nan,srp_neighbor_error_deg=np.nan,
          srp_secondary_angle_deg=np.nan,srp_secondary_peak_ratio=np.nan,active_frames=0,lost_packets=np.nan)
        try:
            info,invalid=inspect(folder); info['recording']=folder.name; inventories.append(info)
            (dest/'integrity.json').write_text(json.dumps(info,indent=2)); row['lost_packets']=info['lost_packets']
            channels=cached_pcm(folder,out,cfg,info['bits'])
            valid=pcm_valid_mask(len(channels[0]),info['bits'],invalid,cfg.numtaps,cfg.decimation)
            p=prepare(channels,valid,cfg,args.start,args.stop,sweep=folder.name.startswith(('sweep_','chirp_')))
            z=p['z']; mask=p['weights']; active=p['active']; f=p['frequencies']
            engine=SpatialEngine(f,cfg)
            row['selection']=p['selection']
            pd.DataFrame(dict(time_s=p['times'],selected_frame=active,ridge_hz=p['ridge'],active_bins=p['mask'].sum(axis=1),
                max_snr=p['snr'].max(axis=1))).to_csv(dest/'frame_selection.csv',index=False)
            br,bp,ba=engine.cross(z,p['broadband_weights'])
            bd,bs=engine.curves(br.sum(axis=0,keepdims=True),bp.sum(axis=0,keepdims=True),ba.sum(keepdims=True))
            row['all_activity_das_angle_deg']=float(cfg.angles[bd[0].argmax()])
            row['all_activity_srp_angle_deg']=float(cfg.angles[bs[0,-1].argmax()])
            raw,phat,auto=engine.cross(z,mask)
            das,srp=engine.curves(raw,phat,auto)
            row['active_frames']=int(active.sum())
            row['available_frames']=len(active)
            row['selected_time_span_s']=float(np.ptp(p['times'][active]))
            for method,curves in [('das',das),('srp',srp[:,-1]),('srp_neighbor',srp[:,0])]:
                peak=peak_summary(curves.sum(axis=0),cfg.angles)
                row[method+'_angle_deg']=peak['angle']; row[method+'_error_deg']=peak['angle']-ref
                row[method+'_ambiguous']=peak['ambiguous']
                row[method+'_secondary_angle_deg']=peak['secondary_angle']
                row[method+'_secondary_peak_ratio']=peak['secondary_ratio']
                row[method+'_stability_std_deg']=float(np.std(cfg.angles[curves[active].argmax(axis=1)]))
            base=[]
            for g in range(1,16):
                peak=peak_summary(srp[:,g-1].sum(axis=0),cfg.angles)
                base.append(dict(recording=folder.name,max_gap=g,baseline_m=g*cfg.spacing,pairs=g*16-g*(g+1)//2,
                    angle_deg=peak['angle'],error_deg=peak['angle']-ref,peak=peak['peak'],secondary_angle_deg=peak['secondary_angle'],
                    secondary_peak=peak['secondary_peak'],secondary_peak_ratio=peak['secondary_ratio'],ambiguous=peak['ambiguous'],
                    stability_std_deg=float(np.std(cfg.angles[srp[active,g-1].argmax(axis=1)]))))
            bdf=pd.DataFrame(base); bdf.to_csv(dest/'baselines.csv',index=False); all_base+=base
            freqrows=[]
            for low,high in BANDS:
                sel=(f>=low)&(f<(high if high<4000 else high+1))
                eligible=(p['mask'][:,sel].sum(axis=1)>=2)
                energy_fraction=float((p['energy'][:,sel]*mask[:,sel]).sum()/max((p['energy']*mask).sum(),1e-30))
                if eligible.sum()<3: continue
                # Same frames for all three estimators in each band.
                au=(abs(z[:, :,sel])**2*mask[:,None,sel]).sum(axis=(1,2))/256
                bd,bs=engine.curves(raw[eligible],phat[eligible],au[eligible],sel)
                fr=dict(recording=folder.name,low_hz=low,high_hz=high,frames=int(eligible.sum()),energy_fraction=energy_fraction)
                for method,curves in [('das',bd),('srp',bs[:,-1]),('srp_neighbor',bs[:,0])]:
                    pk=peak_summary(curves.sum(axis=0),cfg.angles)
                    fr.update({method+'_angle_deg':pk['angle'],method+'_error_deg':pk['angle']-ref,
                      method+'_secondary_peak_ratio':pk['secondary_ratio'],method+'_stability_std_deg':float(np.std(cfg.angles[curves.argmax(axis=1)]))})
                freqrows.append(fr)
            fdf=pd.DataFrame(freqrows); fdf.to_csv(dest/'frequency.csv',index=False); all_freq+=freqrows
            tdf=pd.DataFrame(time_rows(p['times'],active,p['energy'],f,mask,das,srp,cfg)); tdf.to_csv(dest/'time.csv',index=False)
            phases,measured,expected=diagnose(z,f,mask,ref,cfg,frequency_output=dest/'phase_frequency.csv')
            for pr in phases: pr['recording']=folder.name
            all_phase+=phases; pd.DataFrame(phases).to_csv(dest/'pair_phase.csv',index=False)
            levels=np.array([np.sqrt(np.mean(np.asarray(x[valid],dtype=float)**2)) for x in channels]); median=np.median(levels)
            for m,x in enumerate(channels):
                related=[r for r in phases if r['mic_i']==m or r['mic_j']==m]
                cr=dict(recording=folder.name,microphone=m,rms=float(levels[m]),dc=float(np.mean(x[valid])),
                    relative_level_db=float(20*np.log10(max(levels[m],1e-20)/max(median,1e-20))),
                    coherence_median=float(np.median([r['coherence'] for r in related])),
                    phase_residual_median_rad=float(np.median([r['phase_residual_rms_rad'] for r in related])))
                cr['pdm_ones_fraction']=info['pdm_ones_fraction'][m]
                cr['suspect']=bool(abs(cr['relative_level_db'])>12 or cr['coherence_median']<.2 or levels[m]<1e-6 or not .05<cr['pdm_ones_fraction']<.95)
                all_chan.append(cr)
            row['status']='ambiguous' if row['das_ambiguous'] or row['srp_ambiguous'] else 'estimated'
            if max(row['das_stability_std_deg'],row['srp_stability_std_deg'],row['srp_neighbor_stability_std_deg'])>10: row['status']+=';temporally_unstable'
            if 'sweep_not_confirmed' in p['selection']: row['status']+=';sweep_not_confirmed'
            if info['issues']: row['status']+=';integrity_unverified'
            if any(c['suspect'] for c in all_chan if c['recording']==folder.name): row['status']+=';channel_warning'
            recording_plots(dest,folder.name,cfg,p,das,srp,bdf,tdf,fdf,measured,expected,ref)
            # Radial R is hypothetical: this diagnostic never changes steering.
            if np.isfinite(distance) and np.isfinite(ref):
                diff=delays(ref,radius=distance)-delays(ref)
                row['hypothetical_radial_max_delay_error_us']=float(np.max(abs(diff))*1e6)
                row['hypothetical_radial_pair_delay_error_us']=float(np.ptp(diff)*1e6)
            print(folder.name, row['status'], 'DAS',row['das_angle_deg'],'SRP',row['srp_angle_deg'],flush=True)
        except Exception as exc:
            row['status']='failed: '+str(exc); (dest/'error.txt').write_text(traceback.format_exc()); print(row['status'],flush=True)
        results.append(row)
        pd.DataFrame(results).to_csv(out/'doa_results.csv',index=False)
    df=pd.DataFrame(results); baseline=pd.DataFrame(all_base); frequency=pd.DataFrame(all_freq); channels=pd.DataFrame(all_chan)
    metrics=summarize(df)
    for name,table in [('metrics',metrics),('baseline_comparison',baseline),('frequency_comparison',frequency),('channel_diagnostics',channels),('pair_diagnostics',pd.DataFrame(all_phase))]: table.to_csv(out/(name+'.csv'),index=False)
    (out/'input_manifest.json').write_text(json.dumps(inventories,indent=2))
    summary_plots(out/'plots',df,baseline)
    from analysis.finalize import refresh
    refresh(out)
    from analysis.grouped_visualization import generate
    generate(root)
    from analysis.audit import audit
    audit(root)
    print(metrics.to_string(index=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',default='.')
    parser.add_argument('--start',type=float,default=0.); parser.add_argument('--stop',type=float)
    run(parser.parse_args())
