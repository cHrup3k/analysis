# Analiza DOA 16 kanałów PDM

Projekt Python do odczytu niezmienionych nagrań, sprawdzania integralności,
konwersji PDM → PCM, porównania DAS i SRP-PHAT oraz diagnostyki sweepów.
Wyniki i cache powstają wyłącznie w `analysis_results/`.

## Uruchomienie

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/doa-matplotlib .venv/bin/python -m pytest -q
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/doa-matplotlib .venv/bin/python main.py
```

W bieżącym środowisku biblioteki DSP są w nadrzędnym venv, a pytest zainstalowano
lokalnie w `.dependencies`:

```bash
PYTHONPATH=.dependencies OPENBLAS_NUM_THREADS=1 /home/matt/fpga/2mic/.venv/bin/python -m pytest -q
OPENBLAS_NUM_THREADS=1 /home/matt/fpga/2mic/.venv/bin/python main.py
```

Zakres czasowy, z zachowaniem globalnej fazy decymacji:

```bash
python main.py --root . --start 1.1 --stop 3.7
```

Cache obejmuje całe kanały PCM, aby kolejne zakresy nie wymagały konwersji.
Konwersja jest blokowa i czyta PDM przez memmap; jednocześnie rozpakowuje tylko
jeden blok jednego kanału. Domyślnie blok ma 16384 próbek PCM oraz halo FIR.
Dla znacznie dłuższych nagrań używać `--start` i `--stop`, ponieważ STFT i krzywe
przestrzenne wybranego zakresu są przechowywane w RAM. Integralność i konwersja
obejmują całe wejście. To nie jest interfejs strumieniowy do nieskończonego STFT.

## Konfiguracja i matematyka

`config.py`: 16 mikrofonów co 4 cm, c=343 m/s, nominalnie PDM 2,5 MHz,
PCM 50 kHz, FIR 2001/20 kHz/Kaiser 8,6, wspólne pasmo 300–4000 Hz,
Hann 4096, FFT 8192, hop 1024, siatka −90…90° co 0,25°.
Nie ma automatycznego strojenia według nazw nagrań.

Pozycje `x_m=(m−7.5)*0.04`. Opóźnienie `tau_m=−x_m*sin(theta)/343`.
DAS mnoży widma przez `exp(+j*2*pi*f*tau_m)` i sumuje energię.
SRP wykorzystuje `Xi*conj(Xj)` oraz ten sam znak kompensacji różnicy opóźnień.
Wersje bezpośrednie w `doa/das.py` i `doa/srp_phat.py` służą też do niezależnego
sprawdzenia przyspieszonego obliczenia dla równomiernej geometrii liniowej.
W `pair_analysis.py` pary o tym samym odstępie są sumowane przed sterowaniem:
nie jest to przybliżenie. PHAT jest wykonywany osobno dla każdej pary.

Wspólna maska energii ogranicza PHAT w cichych prążkach. Tło to 20. percentyl
energii każdej częstotliwości w czasie; próg wynosi 3×tło. Wymagana jest lokalna
koherencja sąsiadów ≥0,4 (3 ramki × 5 prążków). Wspólne wagi dla obu metod są
proporcjonalne do nadwyżki SNR, normalizowanej maksimum ramki.
Dla sweep/chirp śledzenie grzbietu działa bez referencji: do 5 maksimów SNR/ramkę,
próg SNR 12, oba kierunki częstotliwości, lokalny przyrost do 6000 Hz/s,
tolerancja cofnięcia 15 Hz, dwie brakujące ramki, minimum 0,5 s i 1000 Hz zakresu.
Jeżeli brak ciągłej trajektorii, detektor stopni szuka ≥2 stabilnych plateaus
z co najmniej 3 ramkami każdy, rozrzutem ≤2 prążki FFT, łącznym zakresem ≥1000 Hz
i koncentracją ≥35% nadwyżki SNR w 5 najsilniejszych prążkach. Taki model
odpowiada krótkim tonom widocznym w rzeczywistych plikach sweep.
To jawne założenia detektora, nie uniwersalna detekcja dowolnego sweepu.
`frame_selection.csv` zapisuje decyzje, a `selection` sposób wyboru.
`all_activity_*` zachowuje wyniki sprzed śledzenia sweepu; brak trajektorii daje
jawną flagę i ogólną analizę. Ten mechanizm zachowuje cichy sweep po głośnym
sygnale z innego kierunku. Nie dobiera fragmentów według poprawności DOA.
Odchylenie DOA między ramkami >10° daje `temporally_unstable` (heurystyka
ostrzeżenia, nie skalibrowany przedział ufności).

Progi są zapisane
w `processing_config.json`. Maska jest heurystyką, a nie potwierdzeniem obecności
konkretnego źródła. Stabilny zakłócający sygnał również może przejść maskę.

Model płaski nie wykorzystuje odległości. Model sferyczny jest dostępny
w `doa.geometry.delays(radius=...)`, a jego różnica opóźnień raportowana jest
wyłącznie diagnostycznie przy jawnej hipotezie radialnej odległości.

## Integralność

`packet_validation.py` porównuje CAŁY strumień zbiorczy z 16 plikami osobnymi.
Strumień to dwubajtowe ramki z kanałami od najmłodszego bitu; osobne pliki
są czasowo MSB-first. To potwierdza logiczne przypisanie kanałów, nie fizyczną
kolejność montażu. Rozmiar pakietu jest wnioskowany z liczby ramek i długości
maski tego nagrania, bez stałej ze starszego sprzętu. Nie zachowano nagłówków
UDP i liczników strat FPGA — raport opisuje te ograniczenia.

Każda próbka PCM, której FIR przecina lukę lub brzeg pliku, jest nieważna.
Ramka STFT musi być w całości poprawna. Oryginały nigdy nie są zapisywane.
SHA256 wszystkich wejść trafia do manifestu. Cache identyfikuje źródło przez
nazwę, rozmiar, mtime_ns, parametry i hash FIR. Po ręcznej zmianie danych
z zachowaniem rozmiaru i mtime należy usunąć wyłącznie odpowiedni cache wyników.

## Wyniki

- `analysis_results/REPORT.md`: raport techniczny z wynikami i ograniczeniami.
- `doa_results.csv`, `metrics.csv`: wszystkie pomiary, także błędne i niejednoznaczne.
- `baseline_comparison.csv`: wszystkie maksymalne odstępy 1…15.
- `frequency_comparison.csv`: pasma z wystarczającą energią.
- `channel_diagnostics.csv`, `pair_diagnostics.csv`: poziomy, fazy i koherencja.
- `filter_characteristics.csv`: porównanie filtrów 1001 i 2001.
- `input_manifest.json`, `processing_config.json`: identyfikacja wejść i ustawienia.
- folder pomiaru: `integrity.json`, `time.csv`, szczegółowe CSV, `phase_frequency.csv`, `frame_selection.csv` i pięć PNG
  z panelami widm kierunkowych, DOA/baza, czas/spektrogram, DOA/błędy/częstotliwość,
  faza/reszta modelu. Zbiorcze PNG są w `plots/`.

Drugie maksimum to maksimum lokalne odległe o ≥5°. Stosunek wysokości liczony
jest względem globalnego minimum krzywej, aby wynik SRP nie zależał od offsetu.
Próg niejednoznaczności: stosunek ≥0,9. `NaN` oznacza brak drugiego maksimum.
Brak drugiego maksimum nie dowodzi małej niepewności szerokiej wiązki.

Metryki błędów nie wykluczają przypadków niejednoznacznych. Wyniki służą ocenie
na tym zbiorze. Najlepsza baza według tych danych nie jest niezależnie zweryfikowaną
konfiguracją. Nie wolno interpretować rozbieżności fazy jako automatycznego dowodu
usterki ani odwracać znaku estymatora w celu dopasowania do folderów.

## Testy

Geometria, liczby par, 11 kątów idealnego źródła szerokopasmowego, odwrócenie
kolejności kanałów, niecałkowite opóźnienia, ciągły sweep z propagacją ułamkową,
odbicie, grating lobe powyżej aliasingu, maskowanie strat z pełnym wsparciem FIR,
MSB i niebajtowe zakresy, zgodność przetwarzania blokowego i pełnego dla różnych
filtrów i bloków, zgodność przyspieszonego DAS/SRP z implementacjami bezpośrednimi.
Losowania mają stałe ziarna; testy nie czytają referencji rzeczywistych nagrań.

## Subploty według rodzaju sygnału

`analysis_results/plots/GROUPED_PLOTS.md` indeksuje zestawienia sweep/chirp/noise.
Każdy PNG porównuje wszystkie nagrania danego rodzaju, z wyjątkiem
`noise_0st_10m`, pominiętego wyłącznie w tych nowych zestawieniach.
Obejmują spektrogramy, fazy i reszty, koherencję, DOA w czasie, niejednoznaczność,
widma DAS/SRP, wpływ bazy i jej stabilność, częstotliwość oraz poziomy kanałów.
Powstają automatycznie przy pełnej analizie. Aby odtworzyć tylko te wykresy
z istniejących danych i cache:

```bash
OPENBLAS_NUM_THREADS=1 python -m analysis.grouped_visualization
```

## Wyłączenie błędnego nagrania z metryk

Na podstawie potwierdzenia użytkownika `noise_0st_10m` jest wyłączone z oceny
jako nieprawidłowo wykonane nagranie. `metrics.csv`, `metrics_by_signal.csv`,
`baseline_metrics.csv`, `frequency_metrics.csv` i raport dotyczą 12 pozostałych
pomiarów. Wszystkie szczegółowe wyniki zachowano, dodając `evaluation_included`
i `evaluation_exclusion_reason`. `metrics_all_recordings.csv` zachowuje
pomocnicze metryki wszystkich 13 pomiarów. Reguła wyłączenia jest jawna
w `analysis/evaluation.py` i `processing_config.json`, bez zmiany estymatorów.
Podsumowania i raport można odtworzyć bez ponownej konwersji PDM:

```bash
OPENBLAS_NUM_THREADS=1 python -m analysis.finalize
```
