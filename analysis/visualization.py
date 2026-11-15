"""All figures are standalone PNG artifacts, using the noninteractive backend."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def save(fig,path):
    fig.tight_layout(); fig.savefig(path,dpi=130); plt.close(fig)

def recording_plots(out,name,cfg,p,das,srp,baselines,time_df,freq_df,phase,expected,ref):
    angles=cfg.angles
    fig,ax=plt.subplots(2,1,figsize=(10,7))
    ax[0].plot(angles,das.sum(axis=0)); ax[0].set_ylabel('DAS power')
    for gap in [1,4,8,15]:
        curve=srp[:,gap-1].sum(axis=0); curve=(curve-curve.min())/max(np.ptp(curve),1e-30)
        ax[1].plot(angles,curve,label=f'max gap {gap}')
    for a in ax:
        if np.isfinite(ref): a.axvline(ref,color='k',ls='--',label='reference')
        a.set_xlabel('DOA [deg]'); a.grid()
    ax[1].legend(); fig.suptitle(name); save(fig,out/'directional_spectra.png')
    fig,ax=plt.subplots(figsize=(9,4)); ax.plot(baselines.max_gap,baselines.angle_deg,'o-')
    if np.isfinite(ref): ax.axhline(ref,color='k',ls='--')
    ax.set(xlabel='Maximum index gap',ylabel='SRP DOA [deg]'); ax.grid(); save(fig,out/'baseline.png')
    fig,ax=plt.subplots(2,1,figsize=(11,7),sharex=True)
    for method in ['das','srp','srp_neighbor']: ax[0].plot(time_df.time_s,time_df[method+'_angle'],'.-',label=method)
    if np.isfinite(ref): ax[0].axhline(ref,color='k',ls='--')
    ax[0].set_ylabel('DOA [deg]'); ax[0].legend()
    ax[1].pcolormesh(p['times'],p['spec_freq'],10*np.log10(p['spectrogram'].T+1e-20),shading='auto',cmap='magma')
    ax[1].plot(time_df.time_s,time_df.dominant_frequency_hz,color='cyan',lw=1)
    ax[1].set(xlabel='Time [s]',ylabel='Frequency [Hz]',ylim=(0,10000)); save(fig,out/'time_and_spectrogram.png')
    fig,ax=plt.subplots(2,1,figsize=(9,7),sharex=True)
    if len(freq_df):
        centers=(freq_df.low_hz+freq_df.high_hz)/2
        for method in ['das','srp','srp_neighbor']:
            ax[0].plot(centers,freq_df[method+'_angle_deg'],'o-',label=method)
            ax[1].plot(centers,freq_df[method+'_error_deg'],'o-',label=method)
    ax[0].set_ylabel('DOA [deg]'); ax[0].legend(); ax[1].set(xlabel='Frequency [Hz]',ylabel='Signed error [deg]'); save(fig,out/'frequency.png')
    fig,ax=plt.subplots(2,1,figsize=(11,7),sharex=True)
    for k in range(15):
        ax[0].plot(p['frequencies'],phase[k],alpha=.5,lw=.6)
        ax[1].plot(p['frequencies'],np.angle(np.exp(1j*(phase[k]-expected[k]))),alpha=.5,lw=.6)
    ax[0].plot(p['frequencies'],expected[0],'k--',label='geometric model'); ax[0].legend()
    ax[0].set_ylabel('Adjacent cross phase [rad]'); ax[1].set(xlabel='Frequency [Hz]',ylabel='Wrapped model residual [rad]'); save(fig,out/'phase.png')

def summary_plots(out,df,baseline):
    fig,ax=plt.subplots(figsize=(12,5)); k=np.arange(len(df))
    ax.plot(k,df.reference_angle_deg,'kx',label='reference')
    for method in ['das','srp','srp_neighbor']: ax.plot(k,df[method+'_angle_deg'],'o',label=method)
    ax.set_xticks(k,df.recording,rotation=65,ha='right'); ax.set_ylabel('DOA [deg]'); ax.legend(); save(fig,out/'comparison.png')
    fig,ax=plt.subplots(figsize=(12,5))
    for method in ['das','srp','srp_neighbor']: ax.plot(k,df[method+'_error_deg'],'o-',label=method)
    ax.set_xticks(k,df.recording,rotation=65,ha='right'); ax.set_ylabel('Signed error [deg]'); ax.legend(); save(fig,out/'errors.png')
    fig,ax=plt.subplots(figsize=(9,4))
    if len(baseline): ax.plot(baseline.groupby('max_gap').error_deg.apply(lambda s:s.abs().mean()),'o-')
    ax.set(xlabel='Maximum index gap',ylabel='In-sample MAE [deg]'); ax.grid(); save(fig,out/'baseline_mae.png')
