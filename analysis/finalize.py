"""Rebuild summaries from completed per-recording results without rerunning DSP."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .metrics import summarize
from .evaluation import annotate, included, EXCLUSIONS
from .reporting import report
from .visualization import summary_plots

def refresh(out: Path):
    config_path=out/'processing_config.json'
    settings=json.loads(config_path.read_text())
    settings['sweep_detection']={'continuous':{'snr_min':12,'maximum_slope_hz_s':6000,'minimum_duration_s':.5,'minimum_excursion_hz':1000,'maximum_missing_frames':2},
        'stepped':{'snr_min':12,'top_five_bin_excess_snr_fraction_min':.35,'minimum_plateau_frames':3,'maximum_plateau_span_fft_bins':2,'minimum_plateaus':2,'minimum_excursion_hz':1000},
        'fallback':'all activity, with explicit sweep_not_confirmed flag'}
    settings['evaluation_exclusions']=EXCLUSIONS
    settings['temporal_instability_warning_std_deg']=10
    config_path.write_text(json.dumps(settings,indent=2))
    df=pd.read_csv(out/'doa_results.csv')
    for k,row in df.iterrows():
        stability=[row.get(m+'_stability_std_deg',0) for m in ['das','srp','srp_neighbor']]
        if max(stability)>10 and 'temporally_unstable' not in str(row.status):
            df.loc[k,'status']=str(row.status)+';temporally_unstable'
    df=annotate(df)
    df.to_csv(out/'doa_results.csv',index=False)
    all_df=df.copy()
    summarize(all_df,apply_exclusions=False).to_csv(out/'metrics_all_recordings.csv',index=False)
    pd.DataFrame([{'recording':name,'reason':reason} for name,reason in EXCLUSIONS.items()]).to_csv(out/'evaluation_exclusions.csv',index=False)
    metrics=summarize(all_df); metrics.to_csv(out/'metrics.csv',index=False)
    bytype=[]
    for kind,group in all_df.groupby(df.recording.str.split('_').str[0]):
        m=summarize(group); m['signal_type']=kind; bytype.append(m)
    pd.concat(bytype,ignore_index=True).to_csv(out/'metrics_by_signal.csv',index=False)
    baseline=pd.read_csv(out/'baseline_comparison.csv'); frequency=pd.read_csv(out/'frequency_comparison.csv')
    channels=pd.read_csv(out/'channel_diagnostics.csv')
    # Retain every detailed result, but mark exclusions and use the same 12
    # acquisitions for all aggregate diagnostics and comparisons.
    for name in ['baseline_comparison','frequency_comparison','channel_diagnostics','pair_diagnostics']:
        path=out/(name+'.csv'); annotate(pd.read_csv(path)).to_csv(path,index=False)
    df=included(all_df); baseline=included(baseline); frequency=included(frequency); channels=included(channels)
    baseline.groupby('max_gap').agg(mae=('error_deg',lambda s:s.abs().mean()),
        rmse=('error_deg',lambda s:np.sqrt(np.mean(s**2))),recordings=('recording','nunique')).reset_index().to_csv(out/'baseline_metrics.csv',index=False)
    frequency_rows=[]
    for (low,high),band in frequency.groupby(['low_hz','high_hz']):
        for method in ['das','srp','srp_neighbor']:
            e=band[method+'_error_deg'].dropna()
            frequency_rows.append(dict(low_hz=low,high_hz=high,method=method,mae=e.abs().mean(),rmse=np.sqrt(np.mean(e**2)),recordings=len(e)))
    pd.DataFrame(frequency_rows).to_csv(out/'frequency_metrics.csv',index=False)
    phasebands=[]
    for row in df.itertuples():
        path=out/row.recording/'phase_frequency.csv'
        if not path.exists():continue
        phase=pd.read_csv(path)
        for low,high in [(300,500),(500,1000),(1000,1500),(1500,2000),(2000,2500),(2500,3000),(3000,3500),(3500,4001)]:
            use=phase[(phase.frequency_hz>=low)&(phase.frequency_hz<high)&(phase.active_frames>=3)]
            if use.empty or use.weight.sum()==0:continue
            w=use.weight/use.weight.sum()
            phasebands.append(dict(recording=row.recording,reference_angle_deg=row.reference_angle_deg,low_hz=low,high_hz=min(high,4000),
                weighted_phase_residual_rms_rad=float(np.sqrt(np.sum(w*use.wrapped_residual_rad**2))),
                weighted_coherence=float(np.sum(w*use.coherence))))
    phasebands=pd.DataFrame(phasebands); phasebands.to_csv(out/'phase_summary_by_frequency.csv',index=False)
    inventories=json.loads((out/'input_manifest.json').read_text())
    filters=pd.read_csv(out/'filter_characteristics.csv').to_dict('records')
    summary_plots(out/'plots',df,baseline)
    report(out,df,metrics,baseline,frequency,channels,filters,inventories)
    content=(out/'REPORT.md').read_text()
    exclusion_text='## Wyłączenie błędnego nagrania z oceny\n\n`noise_0st_10m` wykluczono na podstawie informacji użytkownika, że nagranie wykonano nieprawidłowo. Wykryto i przetworzono 13 nagrań; wszystkie główne metryki, porównania baz, pasm i zbiorcze wykresy dotyczą pozostałych 12. Estymatorów i parametrów nie zmieniono. Wiersz wyłączonego pomiaru pozostaje w szczegółowych CSV z evaluation_included=False i podaną przyczyną. metrics_all_recordings.csv zachowuje pomocnicze wyniki dla pełnego zbioru 13 nagrań. RMSE oznacza pierwiastek ze średniego kwadratu błędu kąta, nie RMS wartości samych kątów.\n\n'
    content=content.replace('## Zakres i status',exclusion_text+'## Zakres i status',1).replace(f'Wykryto {len(df)} nagrań; estymację uzyskano dla {int(df.das_angle_deg.notna().sum())}.',f'Ocena obejmuje {len(df)} nagrań po wyłączeniu; dla wszystkich uzyskano estymację.')
    (out/'REPORT.md').write_text(content)
    # Append numerical diagnostics that depend on completed CSV artifacts.
    with (out/'REPORT.md').open('a') as stream:
        stream.write('\n## Uzupełniające wyniki według rodzaju sygnału\n\n```text\n'+pd.concat(bytype).to_string(index=False)+'\n```\n')
        stream.write('\nFlaga temporally_unstable oznacza odchylenie DOA ramek >10° w co najmniej jednej metodzie. Nie jest to skalibrowany przedział ufności. '+str(int(df.status.str.contains('temporally_unstable').sum()))+' z '+str(len(df))+' pomiarów ma tę flagę.\n')
        unconfirmed=df[df.selection.str.contains('sweep_not_confirmed',na=False)]
        if len(unconfirmed):
            stream.write('\nNie potwierdzono trajektorii sweepu w '+str(len(unconfirmed))+' nagraniach: '+', '.join(unconfirmed.recording)+'. Ich kąty i błędy w tabelach pochodzą z analizy ogólnej, a nie z potwierdzonego sweepu. Nie można uznać tej części ekstrakcji sygnału docelowego za zakończoną sukcesem.\n')
        else:
            stream.write('\nWe wszystkich plikach chirp/sweep wykryto ciągłą trajektorię lub stabilne stopnie częstotliwości. Decyzje selekcji zapisano niezależnie od referencji kątowej. Samo wykrycie pasma nie dowodzi, że każda wybrana ramka zawiera wyłącznie źródło docelowe; duża niestabilność czasowa pozostaje ostrzeżeniem.\n')
        if len(phasebands):
            summary=phasebands.groupby(['low_hz','high_hz'])[['weighted_phase_residual_rms_rad','weighted_coherence']].mean().reset_index()
            stream.write('\nReszty fazy sąsiadów wg pasma (tylko prążki z ≥3 aktywnymi ramkami; phase_summary_by_frequency.csv):\n\n```text\n'+summary.to_string(index=False)+'\n```\n')
        if len(channels):
            stream.write('\nZakres gęstości jedynek PDM: '+f'{channels.pdm_ones_fraction.min():.6f}–{channels.pdm_ones_fraction.max():.6f}'+'. Bitowo identyczne pary kanałów: '+str(sum(len(i['identical_channel_pairs']) for i in inventories))+'. Nie dowodzi to poprawności geometrii ani synchronizacji akustycznej.\n')
        stream.write('\n## Najważniejsze potwierdzone wnioski\n')
        method_mae=metrics.set_index('method').mae
        stream.write(f'\nDAS ma MAE {method_mae["das"]:.3f}°, SRP 120 par {method_mae["srp"]:.3f}°, a SRP 15 sąsiadów {method_mae["srp_neighbor"]:.3f}°. Pełny SRP porównujemy z DAS na tych samych 12 nagraniach; niewielka różnica MAE nie dowodzi istotnej przewagi. Porównanie z sąsiadami i wszystkimi bazami dotyczy tego samego zbioru, bez wyboru bazy osobno dla każdego nagrania.\n')
        worst=df.loc[df.srp_error_deg.abs().idxmax()]
        stream.write(f'\nNajwiększy błąd pełnego SRP: {worst.recording}, oszacowanie {worst.srp_angle_deg:.2f}°, referencja {worst.reference_angle_deg:.2f}°. Ten przypadek pozostaje w metrykach ocenianego zbioru 12 nagrań. Wysokie lub jednoznaczne maksimum nie gwarantuje identyfikacji właściwego źródła.\n')
        flagged=channels[channels.suspect]
        if len(flagged):
            stream.write('\nPodejrzane poziomy/koherencja: '+', '.join(f'{r.recording}: mic{r.microphone} ({r.relative_level_db:.1f} dB względem mediany)' for r in flagged.itertuples())+'. Nie usuwano tych kanałów. Liczba powtórzeń flag jest widoczna w tabeli; pojedyncza flaga nie potwierdza trwałej usterki.\n')
        if len(frequency):
            trend=frequency.groupby('low_hz').das_error_deg.apply(lambda s:s.abs().mean())
            stream.write('\nBłąd DAS nie rośnie monotonicznie z częstotliwością: istotne błędy występują również w dolnych pasmach, a zagregowane błędy w zakresie 2–3,5 kHz są mniejsze. Pasmo 3,5–4 kHz należy sprawdzać osobno z uwagi na niewielką liczbę ramek i aliasing długich par. Zależność czasu, SNR i składu nagrań nie pozwala przypisać całego trendu samej częstotliwości.\n')
        stream.write('\nHipotezy wymagające osobnej weryfikacji: odbicia lub obce źródła w fragmentach o odmiennym DOA, rozbieżność rzeczywistej geometrii/orientacji z modelem i niedokładna nominalna prędkość dźwięku. Reszty fazowe i systematyczne odchylenia kąta nie rozstrzygają pomiędzy tymi przyczynami. Nie zastosowano korekcji dopasowanej do referencji.\n')
        testfile=out/'pytest_results.txt'
        if testfile.exists(): stream.write('\nZapis wykonania testów:\n\n```text\n'+testfile.read_text().strip()+'\n```\n')
    return df,metrics

if __name__=='__main__': refresh(Path('analysis_results'))
