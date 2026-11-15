"""Comparison panels by signal type; exclusions affect only these figures.

Run: python -m analysis.grouped_visualization [--root PATH]
Uses cached PCM and existing CSV diagnostics. Original results remain unchanged.
"""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/doa-matplotlib')
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal.windows import hann
from config import Config
from pdm_processing.decimation import cached_pcm
from pdm_processing.packet_validation import pcm_valid_mask
from pdm_processing.signal_preparation import prepare
from doa.pair_analysis import SpatialEngine

METHODS={'das':'DAS','srp':'SRP 120 par','srp_neighbor':'SRP 15 sąsiadów'}
EXCLUDED={'noise_0st_10m'}

def panel_grid(records, title, xlabel, ylabel):
    fig,axes=plt.subplots((len(records)+1)//2,2,figsize=(15,4.2*((len(records)+1)//2)),squeeze=False,layout='constrained')
    flat=axes.ravel()
    for ax,record in zip(flat,records):
        ax.set(title=record['name'],xlabel=xlabel,ylabel=ylabel)
        ax.grid(alpha=.2)
    for ax in flat[len(records):]:ax.set_visible(False)
    fig.suptitle(title,fontsize=16)
    return fig,flat[:len(records)]

def save(fig,path):
    fig.savefig(path,dpi=160); plt.close(fig)

def reference(ax,angle,vertical=False):
    if np.isfinite(angle):
        (ax.axvline if vertical else ax.axhline)(angle,color='k',ls='--',lw=1,label='Referencja')

def generate(root: Path) -> list[Path]:
    out=root/'analysis_results'; plots=out/'plots'; plots.mkdir(exist_ok=True)
    settings=json.loads((out/'processing_config.json').read_text()); cfg=Config(**settings['config'])
    results=pd.read_csv(out/'doa_results.csv'); channel=pd.read_csv(out/'channel_diagnostics.csv')
    generated=[]; included={}
    for kind in ['sweep','chirp','noise']:
        group=results[results.recording.str.startswith(kind+'_') & ~results.recording.isin(EXCLUDED)]
        group=group.sort_values(['reference_angle_deg','recording'])
        records=[]
        for row in group.itertuples():
            if not np.isfinite(row.das_angle_deg):continue
            name=row.recording; folder=root/name; detail=out/name
            print('Grouped plots:',name,flush=True)
            info=json.loads((detail/'integrity.json').read_text())
            invalid=[]
            if info.get('packet_size_confirmed'):
                valid=np.fromfile(folder/'packet_valid.bin',dtype='uint8'); spp=info['samples_per_packet_inferred']
                invalid=[(int(k*spp),int((k+1)*spp)) for k in np.flatnonzero(valid==0)]
            channels=cached_pcm(folder,out,cfg,info['bits'])
            valid=pcm_valid_mask(len(channels[0]),info['bits'],invalid,cfg.numtaps,cfg.decimation)
            p=prepare(channels,valid,cfg,settings.get('start',0),settings.get('stop'),sweep=kind!='noise')
            engine=SpatialEngine(p['frequencies'],cfg)
            raw,phat,auto=engine.cross(p['z'],p['weights'])
            das,srp=engine.curves(raw.sum(axis=0,keepdims=True),phat.sum(axis=0,keepdims=True),auto.sum(keepdims=True))
            # One-sided PSD, referenced to squared PDM full-scale units per Hz.
            psd=p['spectrogram']/(cfg.pcm_fs*np.sum(hann(cfg.frame_size,sym=False)**2))
            psd[:,1:]*=2
            records.append(dict(name=name,reference=row.reference_angle_deg,p=p,psd=10*np.log10(np.maximum(psd,1e-30)),
                das=das[0],srp=srp[0],time=pd.read_csv(detail/'time.csv'),frequency=pd.read_csv(detail/'frequency.csv'),
                baseline=pd.read_csv(detail/'baselines.csv'),phase=pd.read_csv(detail/'phase_frequency.csv'),
                channels=channel[channel.recording==name]))
        if not records:continue
        included[kind]=[r['name'] for r in records]
        def finish(fig,label):
            path=plots/f'{kind}_{label}_subplots.png';save(fig,path);generated.append(path)
        fig,axes=panel_grid(records,f'{kind}: spektrogramy mic0 (wspólna skala PSD)','Czas [s]','Częstotliwość [Hz]')
        vmax=max(float(np.max(r['psd'])) for r in records); vmin=vmax-90
        for ax,r in zip(axes,records):
            p=r['p']; im=ax.pcolormesh(p['times'],p['spec_freq'],r['psd'].T,shading='auto',cmap='magma',vmin=vmin,vmax=vmax)
            ax.axhline(cfg.freq_max,color='white',ls=':',lw=.8)
            ridge=p['ridge']; ax.plot(p['times'],ridge,color='cyan',lw=1,label='Wykryty grzbiet')
            ax.set_ylim(0,10000);ax.grid(False)
        fig.colorbar(im,ax=list(axes),label='PSD [dBFS/Hz], nominalna skala PDM ±1')
        finish(fig,'spectrograms')
        for label,column,ylabel in [('doa_time','angle','DOA [°]'),('ambiguity_time','secondary_ratio','Stosunek drugiego maksimum')]:
            fig,axes=panel_grid(records,f'{kind}: '+('DOA w czasie' if label=='doa_time' else 'niejednoznaczność w czasie'),'Czas [s]',ylabel)
            for ax,r in zip(axes,records):
                t=r['time']
                for method,name in METHODS.items():ax.plot(t.time_s,t[method+'_'+column],'.-',ms=3,label=name)
                if label=='doa_time':reference(ax,r['reference']);ax.set_ylim(-95,95)
                else:ax.axhline(.9,color='k',ls='--',label='Próg 0,9');ax.set_ylim(0,1.05)
                ax.legend(fontsize=8)
            finish(fig,label)
        for label in ['das_spectrum','srp_spectra']:
            fig,axes=panel_grid(records,f'{kind}: '+('widma DAS' if label=='das_spectrum' else 'widma SRP-PHAT'),'Kąt [°]','Wynik znormalizowany')
            for ax,r in zip(axes,records):
                curves=[('DAS',r['das'])] if label=='das_spectrum' else [(f'Maks. odstęp {g}',r['srp'][g-1]) for g in [1,4,8,15]]
                for name,curve in curves:ax.plot(cfg.angles,(curve-curve.min())/max(np.ptp(curve),1e-30),label=name)
                reference(ax,r['reference'],True);ax.set(xlim=(-90,90),ylim=(0,1.05));ax.legend(fontsize=8)
            finish(fig,label)
        for label,column,ylabel in [('baseline_doa','angle_deg','DOA [°]'),('baseline_stability','stability_std_deg','Odchylenie DOA ramek [°]')]:
            fig,axes=panel_grid(records,f'{kind}: '+('DOA a długość bazy' if label=='baseline_doa' else 'stabilność a długość bazy'),'Maksymalny odstęp indeksów',ylabel)
            for ax,r in zip(axes,records):
                b=r['baseline'];ax.plot(b.max_gap,b[column],'o-');ax.set_xticks([1,2,4,6,8,10,12,15])
                if label=='baseline_doa':reference(ax,r['reference']);ax.set_ylim(-95,95)
                else:ax.set_ylim(bottom=0)
            finish(fig,label)
        for label,column,ylabel in [('frequency_doa','angle_deg','DOA [°]'),('frequency_error','error_deg','Błąd ze znakiem [°]')]:
            fig,axes=panel_grid(records,f'{kind}: '+('DOA względem częstotliwości' if label=='frequency_doa' else 'błąd względem częstotliwości'),'Środek pasma [Hz]',ylabel)
            for ax,r in zip(axes,records):
                f=r['frequency'];centers=(f.low_hz+f.high_hz)/2
                for method,name in METHODS.items():ax.plot(centers,f[method+'_'+column],'o-',ms=3,label=name)
                reference(ax,r['reference'] if label=='frequency_doa' else 0)
                ax.set_xlim(300,4000);ax.legend(fontsize=8)
                if label=='frequency_doa':ax.set_ylim(-95,95)
            finish(fig,label)
        for label,column,ylabel in [('phases','measured_phase_rad','Faza widma wzajemnego [rad]'),('phase_residuals','wrapped_residual_rad','Zawinięta reszta fazy [rad]')]:
            fig,axes=panel_grid(records,f'{kind}: '+('fazy par sąsiednich i model referencyjny' if label=='phases' else 'reszty fazy względem modelu'),'Częstotliwość [Hz]',ylabel)
            for ax,r in zip(axes,records):
                phase=r['phase'];shown=False
                for mic,pair in phase.groupby('mic_i'):
                    pair=pair.sort_values('frequency_hz');valid=(pair.active_frames>=3)&(pair.weight>0)
                    # NaNs preserve gaps rather than joining unsupported bins.
                    ax.plot(pair.frequency_hz,pair[column].where(valid),lw=.8,alpha=.7,color=plt.cm.viridis(mic/14))
                    if not shown and valid.any():
                        if label=='phases':ax.plot(pair.frequency_hz,pair.predicted_phase_rad,'k--',lw=1.3,label='Model referencyjny')
                        shown=True
                if label=='phase_residuals':ax.axhline(0,color='k',ls='--',lw=1)
                ax.set(xlim=(300,4000),ylim=(-np.pi,np.pi),yticks=[-np.pi,0,np.pi],yticklabels=['−π','0','π'])
                if label=='phases' and shown:ax.legend(fontsize=8)
            finish(fig,label)
        fig,axes=panel_grid(records,f'{kind}: koherencja sąsiednich par (≥3 aktywne ramki)','Częstotliwość [Hz]','Para: m → m+1')
        for ax,r in zip(axes,records):
            phase=r['phase'].copy();phase.loc[(phase.active_frames<3)|(phase.weight<=0),'coherence']=np.nan
            grid=phase.pivot(index='mic_i',columns='frequency_hz',values='coherence').sort_index()
            im=ax.pcolormesh(grid.columns.to_numpy(),grid.index.to_numpy(),grid.to_numpy(),vmin=0,vmax=1,shading='nearest',cmap='viridis')
            ax.set_yticks([0,3,6,9,12,14]);ax.grid(False)
        fig.colorbar(im,ax=list(axes),label='Koherencja');finish(fig,'coherence')
        fig,axes=panel_grid(records,f'{kind}: poziomy wszystkich 16 kanałów','Numer mikrofonu','RMS względem mediany [dB]')
        for ax,r in zip(axes,records):
            c=r['channels'];ax.bar(c.microphone,c.relative_level_db,color=np.where(c.suspect,'tab:red','tab:blue'))
            ax.axhline(-12,color='k',ls='--',lw=.8);ax.axhline(12,color='k',ls='--',lw=.8);ax.set_xticks(range(0,16,2))
        finish(fig,'channel_levels')
    index=plots/'GROUPED_PLOTS.md'
    lines=['# Zbiorcze subploty według rodzaju sygnału','',
        'Pominięto wyłącznie `noise_0st_10m` w nowych zestawieniach. Szczegółowe dane zachowano; aktualne zasady wyłączenia z metryk opisano w REPORT.md.',
        'Spektrogramy mają wspólną skalę PSD w obrębie rodzaju sygnału (90 dB zakresu); linia 4 kHz oznacza górną granicę analizy DOA. Cyjan: wykryty grzbiet.',
        'Fazy i koherencja pokazują wyłącznie prążki z co najmniej 3 aktywnymi ramkami. Kolory faz odpowiadają 15 parom sąsiednim; braki wsparcia pozostają puste.',
        'Widma kierunkowe są normalizowane osobno względem swojego minimum i maksimum. Nie porównuj ich jako bezwzględnych poziomów energii.','']
    for kind,names in included.items():
        lines.extend([f'## {kind}','',', '.join(f'`{n}`' for n in names),''])
        lines.extend(f'- [{p.stem}]({p.name})' for p in generated if p.name.startswith(kind+'_'));lines.append('')
    index.write_text('\n'.join(lines))
    (plots/'grouped_manifest.json').write_text(json.dumps({'included':included,'excluded':sorted(EXCLUDED),'files':[p.name for p in generated]},indent=2))
    return generated

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',default='.')
    args=parser.parse_args();print(f'Generated {len(generate(Path(args.root).resolve()))} figures')
