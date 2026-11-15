# Analiza DOA — 16 mikrofonów PDM

## Wyłączenie błędnego nagrania z oceny

`noise_0st_10m` wykluczono na podstawie informacji użytkownika, że nagranie wykonano nieprawidłowo. Wykryto i przetworzono 13 nagrań; wszystkie główne metryki, porównania baz, pasm i zbiorcze wykresy dotyczą pozostałych 12. Estymatorów i parametrów nie zmieniono. Wiersz wyłączonego pomiaru pozostaje w szczegółowych CSV z evaluation_included=False i podaną przyczyną. metrics_all_recordings.csv zachowuje pomocnicze wyniki dla pełnego zbioru 13 nagrań. RMSE oznacza pierwiastek ze średniego kwadratu błędu kąta, nie RMS wartości samych kątów.

## Zakres i status

Ocena obejmuje 12 nagrań po wyłączeniu; dla wszystkich uzyskano estymację. Błędy i niejednoznaczności pozostają w tabelach. Wyniki są oceną na tym zbiorze, bez niezależnego zbioru walidacyjnego.

## Konwersja i integralność

Całe pliki zbiorcze porównano bit po bicie z mic0…mic15. Dwa bajty na chwilę PDM, kanały 0–7 w pierwszym bajcie i 8–15 w drugim, od bitu najmłodszego; pliki osobne MSB-first. SHA256 wejść zapisano w input_manifest.json. Zgodność potwierdza logiczną kolejność kanałów i pakowanie, nie fizyczne położenia mikrofonów.

Potwierdzono deinterleaving w 13 nagraniach. Rozmiar pakietu wywnioskowano z dokładnego ilorazu liczby ramek i długości maski: [688] próbek PDM. Nie zachowano nagłówków UDP; jest to silna zgodność strukturalna, nie niezależny pomiar pakietyzacji.

Straty hosta: 0 pakietów. Brak zapisanych liczników strat wewnątrz FPGA. Zegar nominalny 2,5 MHz jest zgodny z dostępnym ../pdm_udp.py, lecz brak metadanych zegara powiązanych z konkretnymi nagraniami.

Konwersja używa symetrycznego FIR i jednej globalnej siatki co 50 bitów. PCM float32, filtracja float64. Bloki mają pełne halo, opóźnienie grupowe jest usuwane poprzez wybór wyjścia splotu w kQ+H. Brzegi i cały wpływ brakujących bitów na FIR są odrzucane; ramki dotykające takich próbek nie są analizowane. Nie stosuje się filtra IIR przenoszącego uszkodzenie poza maskę. Filtr pasmowy analizy jest realizowany przez wybór prążków 300–4000 Hz.

Charakterystyka FIR (względem 0 dB):

```text
 numtaps  group_delay_pdm  group_delay_s  passband_0_4k_max_loss_db  passband_0_15k_max_loss_db  stopband_from_25k_db  symmetry_error
    1001            500.0         0.0002                   0.000048                    0.094126             39.320868             0.0
    2001           1000.0         0.0004                   0.000001                    0.000092             88.681234             0.0
```

Filtr 2001 współczynników wybrano dla większego tłumienia przy 25 kHz niż wersja 1001. Ma fazę liniową, identyczną dla wszystkich kanałów. Granice pasm 15–25 kHz wyznaczają konserwatywny obszar przejściowy. Testy porównują pełny splot i bloki również dla niebajtowych początków zakresu.

## Model i maski

M=16, d=0,04 m, apertura 0,60 m, c=343 m/s. τm=−xm sinθ/c, kompensacja exp(+j2πfτm). Znaku nie zmieniano na podstawie referencji. Syntetyczne źródła generowane są z opóźnień propagacji. Układ liniowy ma nierozróżnialność przód–tył.

Hann 4096, FFT 8192, hop 1024. Wspólna maska wymaga energii prążka ≥3×20. percentyla energii tej częstotliwości w czasie i SNR ≥1% maksimum SNR ramki; ramka wymaga ≥2 aktywnych prążków oraz lokalnej średniej koherencji sąsiadów ≥0,4 (3 ramki × 5 prążków). Wagi wspólne dla DAS/SRP są proporcjonalne do nadwyżki SNR, normalizowanej maksimum ramki. Nie ma progu względem maksymalnej energii całego nagrania, który odrzucałby cichy sweep po silnym impulsie. To heurystyka energetyczna, nie detektor gwarantujący odróżnienie szerokopasmowego szumu źródła od tła. Ciągłe nagrania noise mogą być aktywne w całości. PHAT ma regularyzację 0,001 maksimum widma pary w ramce. Nie użyto referencji ani kalibracji fazowej w estymatorach.

DAS jest sumą energii skompensowanych sygnałów. Obliczenia przyspieszono dokładną tożsamością energii sumy i pogrupowaniem par według odstępu, bez zmiany matematyki. SRP sumuje niezależnie znormalizowane widma wzajemne. DAS zachowuje wagę energii, PHAT usuwa amplitudę widma pary, a oba dostają tę samą dodatkową wagę wiarygodności prążka; wspólne pozostają ramki, pasmo i maska.

Drugie maksimum oznacza lokalne maksimum oddalone o co najmniej 5°. Stosunek to (P2−min P)/(P1−min P); próg niejednoznaczności 0,9. Brak drugiego maksimum daje NaN. Ta miara opisuje konkurencyjne płaty, a nie szerokość jednego szerokiego maksimum. Odchylenie DOA między ramkami jest osobną miarą stabilności.

## Wybór sweepu bez referencji

Dla nazw sweep/chirp zastosowano dynamiczne śledzenie do pięciu lokalnych maksimów SNR na ramkę. Próg SNR 12, maksymalna lokalna prędkość 6000 Hz/s, tolerancja cofnięcia 15 Hz, do dwóch brakujących ramek, czas ≥0,5 s i zakres ≥1000 Hz. Wybierana jest najdłuższa spójna trajektoria rosnąca lub malejąca, nie trajektoria pasująca do DOA. Pasmo wokół niej uwzględnia rozmycie Hanna i lokalną prędkość sweepu. Są to jawne założenia detektora, nie uniwersalny model dowolnego sygnału. Gdy brak ciągłej trajektorii, sprawdzane są stopnie częstotliwości: maksimum SNR ≥12, co najmniej 35% nadwyżki SNR w pięciu najsilniejszych prążkach, ≥3 ramki w plateau, rozrzut częstotliwości ≤2 prążki FFT, ≥2 plateaus o łącznym zakresie ≥1000 Hz. Ten detektor pozwala analizować krótkie tony w nagraniach nazwanych sweep; szerokopasmowy impuls nie spełnia kryterium koncentracji. Jeśli oba detektory zawodzą, zachowuje się ogólną analizę i oznacza sweep_not_confirmed. frame_selection.csv zachowuje decyzje dla wszystkich ramek.

Pierwsza analiza z progiem względem maksimum całego nagrania odrzucała cichszy sweep po silnych wczesnych sygnałach. Końcowa wersja wykorzystuje tło osobno dla każdej częstotliwości. Selekcję poprawiono po diagnostyce widm; nie jest to niezależna walidacja detektora na nowych nagraniach. Nie używano kąta referencyjnego do tej selekcji. all_activity_* w głównym CSV zachowuje wyniki dla wszystkich prążków aktywnych przed śledzeniem sweepu.

## Dokładność wszystkich metod

```text
      method      mae     rmse  median_absolute_error  p90_absolute_error  analyzed  excluded  ambiguous  temporally_unstable  rejected
         das 2.666667 3.010399                   2.75               4.225        12         1          0                    8         0
         srp 2.645833 3.033665                   2.75               4.250        12         1          0                    8         0
srp_neighbor 3.416667 4.592793                   2.75               6.825        12         1          0                    7         0
```

```text
      recording  reference_angle_deg  das_angle_deg  srp_angle_deg  srp_neighbor_angle_deg                        status
chirp_+60st_10m                 60.0          64.25          64.75                   60.25 estimated;temporally_unstable
chirp_-30st_10m                -30.0         -31.25         -31.00                  -32.50 estimated;temporally_unstable
chirp_-45st_10m                -45.0         -49.00         -48.75                  -47.75 estimated;temporally_unstable
  chirp_0st_10m                  0.0           2.00           2.00                    3.25 estimated;temporally_unstable
noise_+60st_10m                 60.0          63.75          63.75                   61.00 estimated;temporally_unstable
noise_-30st_10m                -30.0         -31.00         -31.00                  -31.00                     estimated
noise_-45st_10m                -45.0         -49.50         -49.25                  -49.00                     estimated
noise_3_0st_10m                  0.0           0.50           0.25                    0.00     estimated;channel_warning
sweep_+60st_10m                 60.0          63.50          63.50                   62.75                     estimated
sweep_-30st_10m                -30.0         -31.50         -31.50                  -18.75 estimated;temporally_unstable
sweep_-45st_10m                -45.0         -49.00         -49.25                  -50.25 estimated;temporally_unstable
  sweep_0st_10m                  0.0           1.75           1.75                    7.00 estimated;temporally_unstable
```

Metryki zawierają także niejednoznaczne estymacje. Odrzucone przypadki są jawnie zliczone; brak referencji nie jest błędem algorytmu. Różnice kątowe liczone są w przedziale widoczności liniowego układu, bez sztucznego zawijania do kierunku przeciwnego.

Najniższe MAE wśród trzech głównych konfiguracji uzyskała srp: 2.646°. Jest to wynik opisowy na tych nagraniach, nie dowód przewagi na nowych danych.

## Długość bazy i aliasing

```text
 max_gap      mae     rmse  mean_stability_deg  ambiguous
       1 3.416667 4.592793           18.791945          0
       2 1.645833 2.142088           20.090413          0
       3 2.562500 2.891258           21.089863          0
       4 2.666667 3.060161           21.665773          0
       5 2.666667 3.029370           21.891439          0
       6 2.645833 3.042237           22.033175          0
       7 2.645833 3.023347           22.059648          0
       8 2.687500 3.091487           22.205264          0
       9 2.687500 3.093171           22.172609          0
      10 2.666667 3.060161           22.187866          0
      11 2.645833 3.033665           22.158223          0
      12 2.666667 3.060161           22.265375          0
      13 2.687500 3.072899           22.146226          0
      14 2.666667 3.060161           22.115830          0
      15 2.645833 3.033665           22.122577          0
```

Najniższe MAE zbiorcze ma odstęp 2. Nie wybierano konfiguracji osobno według referencji nagrania. Wybór na podstawie tej tabeli wymaga walidacji na innym zbiorze. Wyniki dla 15 sąsiadów i 120 par są bezpośrednio porównane powyżej.

Graniczne c/(2d)=4287,5 Hz dotyczy sąsiadów. Dla odstępu g granica pary wynosi 4287,5/g Hz. Suma wielu par może usuwać część niejednoznaczności, lecz nie gwarantuje tego dla wąskopasmowego sweepu. Główne wyniki ograniczono do 4 kHz. Spektrogram do 10 kHz jest wyłącznie diagnostyczny.

## Zależność od częstotliwości

```text
 low_hz  high_hz   das_mae   srp_mae  recordings
    300      500 77.937500 62.250000           4
    500     1000 31.361111 31.083333           9
   1000     1500 16.025000 15.975000          10
   1500     2000  2.479167  2.583333          12
   2000     2500  2.437500  2.416667          12
   2500     3000  2.770833  2.770833          12
   3000     3500  2.625000  2.750000          12
   3500     4000 13.416667 13.250000           9
```

Pasma wymagają co najmniej trzech aktywnych ramek z przynajmniej dwoma prążkami spełniającymi maskę SNR/koherencji. Udział energii raportowany jest opisowo; nie odrzuca się cichego pasma tylko z powodu silnego impulsu w innym paśmie. frequency_comparison.csv zawiera także niejednoznaczności i stabilność. Brak pasma oznacza brak wystarczających danych. Nie należy utożsamiać trendu zbiorczego z izolowanym wpływem częstotliwości: zmieniają się czas sweepu, SNR i odbicia.

## Zależność od kąta i wybór fragmentu

```text
 reference_angle_deg  das_error_deg  srp_error_deg  srp_neighbor_error_deg
               -45.0       4.166667       4.083333                4.000000
               -30.0       1.250000       1.166667                4.916667
                 0.0       1.416667       1.333333                3.416667
                60.0       3.833333       4.000000                1.333333
```

```text
      recording             selection  active_frames  das_stability_std_deg  srp_stability_std_deg  all_activity_das_angle_deg  all_activity_srp_angle_deg
chirp_+60st_10m   tracked_sweep_ridge             88              10.540050              10.739021                        4.00                      -83.00
chirp_-30st_10m   tracked_sweep_ridge             96              32.959630              34.339229                       -2.50                      -83.25
chirp_-45st_10m   tracked_sweep_ridge            100              40.228107              39.506574                       -1.50                      -50.75
  chirp_0st_10m   tracked_sweep_ridge             97              19.008982              19.246521                        1.50                      -80.25
noise_+60st_10m  energy_and_coherence            240              55.615448              34.312056                       63.75                       63.75
noise_-30st_10m  energy_and_coherence            240               0.128759               0.101529                      -31.00                      -31.00
noise_-45st_10m  energy_and_coherence            240               0.447427               0.145681                      -49.50                      -49.25
noise_3_0st_10m  energy_and_coherence            240               0.197837               0.167964                        0.50                        0.25
sweep_+60st_10m tracked_stepped_sweep             10               0.691014               0.640312                        9.50                       61.25
sweep_-30st_10m tracked_stepped_sweep             18              44.547355              46.056085                       -2.75                      -66.00
sweep_-45st_10m tracked_stepped_sweep             43              50.105665              50.971573                        0.50                      -75.50
  sweep_0st_10m tracked_stepped_sweep             16              30.829404              29.244386                       -0.75                      -77.25
```

Kolumny all_activity pokazują, czy wynik zmienia się po ograniczeniu analizy do widocznego sweepu. Duża zmiana dowodzi wrażliwości na wybór sygnału, a nie sama w sobie usterki sprzętu. Odchylenie między ramkami obejmuje także wąskopasmowe niejednoznaczności. Wspólny błąd znaku lub skali nie został korygowany na podstawie etykiet.

## Kanały, fazy i możliwe problemy

```text
 microphone  suspect_count  median_coherence  median_phase_residual_rad  mean_relative_db
          0              0          0.975326                   0.589497         -4.245846
          1              0          0.980309                   0.614930          4.044828
          2              0          0.984467                   0.556483         -0.906745
          3              0          0.983627                   0.486485         -1.190505
          4              0          0.983819                   0.395606         -0.817352
          5              0          0.983145                   0.353225          0.643639
          6              0          0.984606                   0.343573          1.562799
          7              0          0.986282                   0.376375         -0.189048
          8              0          0.985895                   0.366023         -2.763336
          9              0          0.979648                   0.351034         -2.838616
         10              1          0.984756                   0.336504          2.130800
         11              0          0.986332                   0.320969          2.537515
         12              0          0.981692                   0.453712          0.049065
         13              0          0.981295                   0.497098          8.311859
         14              0          0.981090                   0.546557          5.753103
         15              1          0.981575                   0.535295         -3.316921
```

Podejrzenie kanału: poziom różniący się o ponad 12 dB od mediany, mediana koherencji <0,2, RMS <1e−6 lub gęstość jedynek PDM poza 5–95%. Kanałów nie usuwano. Koherencja jest estymowana z wielu aktywnych ramek, a nie z jednej realizacji iloczynu widm. Reszta fazy jest zawijana przez arg exp(jΔφ). pair_diagnostics.csv pozwala porównać każdą parę pomiędzy kierunkami. phase_frequency.csv zachowuje fazę, resztę i koherencję sąsiadów w każdym prążku oraz liczbę aktywnych ramek; koherencja oparta na jednej ramce jest obciążona i nie potwierdza synchronizacji. Zmienność reszt z kierunkiem/częstotliwością nie identyfikuje jednoznacznie usterki; możliwe są odbicia, błąd fizycznego przypisania kanałów, pozycjonowania źródła lub synchronizacji. Bez pomiaru kalibracyjnego nie rozstrzygamy przyczyny.

## Stabilność i pole bliskie

Każde nagranie ma time.csv oraz wykres czas–DOA i spektrogram z dominującą częstotliwością. Okna 0,5 s, hop 0,25 s grupują wspólne ramki STFT według ich środków; energia ramki ma wsparcie ±40,96 ms wokół środka. Wynik całego nagrania może ukrywać ruch maksimum — należy sprawdzać odchylenia i wykresy czasowe.

```text
      recording  hypothetical_radial_max_delay_error_us  hypothetical_radial_pair_delay_error_us
chirp_+60st_10m                                3.367171                                 3.352619
chirp_-30st_10m                                9.987756                                 9.944068
chirp_-45st_10m                                6.701149                                 6.672036
  chirp_0st_10m                               13.116583                                13.058274
noise_+60st_10m                                3.367171                                 3.352619
noise_-30st_10m                                9.987756                                 9.944068
noise_-45st_10m                                6.701149                                 6.672036
noise_3_0st_10m                               13.116583                                13.058274
sweep_+60st_10m                                3.367171                                 3.352619
sweep_-30st_10m                                9.987756                                 9.944068
sweep_-45st_10m                                6.701149                                 6.672036
  sweep_0st_10m                               13.116583                                13.058274
```

Powyższe opóźnienia porównują model sferyczny i płaski WYŁĄCZNIE przy hipotetycznej interpretacji odległości jako radialnej. Nie użyto ich do estymacji. Dla 10 m i broadside krzywizna na skraju wynosi około 13,1 µs (około 0,33 rad przy 4 kHz), zatem przybliżenie nie jest dokładne mimo dużej odległości.

## Zalecenia i granice wnioskowania

Zweryfikować fizyczną kolejność, współrzędne i orientację mikrofonów oraz referencję kątową niezależnym pomiarem. Zachowywać nagłówki UDP, częstotliwość zegara i liczniki FPGA. Przeprowadzić pomiar kalibracyjny z wieloma kątami i odległościami, w tym pomiar bez odbić; nie korygować opóźnień na podstawie tego zbioru. Zweryfikować ewentualne różne zbocza próbkowania kanałów współdzielących DATA w konkretnym firmware. Takiej korekcji tutaj nie zastosowano.

Dobór pasma/bazy oceniać na osobnym zbiorze. Dla sweepu rozważyć estymację wspólną na dłuższym fragmencie trajektorii częstotliwości i modele odbić, zamiast ufać pojedynczemu wąskopasmowemu maksimum. Prędkość dźwięku można poprawić na podstawie zmierzonej temperatury. Porównać model sferyczny dopiero po potwierdzeniu znaczenia odległości.

## Artefakty i odtwarzalność

doa_results.csv, metrics.csv, baseline_comparison.csv, frequency_comparison.csv, channel_diagnostics.csv, pair_diagnostics.csv; szczegóły i PNG w folderach pomiarów; zbiorcze wykresy w plots/. processing_config.json zapisuje ustawienia. Cache zawiera konfigurację FIR, hash współczynników i identyfikację wejść (rozmiar i mtime); manifest dodatkowo pełne SHA256. Oryginały otwierane są wyłącznie do odczytu.

Walidacja syntetyczna i konwersji: patrz pytest_results.txt. Testy syntetyczne dowodzą zgodności matematycznej implementacji przy modelu idealnym; nie potwierdzają poprawności fizycznego montażu.

## Uzupełniające wyniki według rodzaju sygnału

```text
      method    mae     rmse  median_absolute_error  p90_absolute_error  analyzed  excluded  ambiguous  temporally_unstable  rejected signal_type
         das 2.8750 3.147420                  3.000               4.175         4         0          0                    4         0       chirp
         srp 2.8750 3.225872                  2.875               4.450         4         0          0                    4         0       chirp
srp_neighbor 2.1875 2.471715                  2.625               3.100         4         0          0                    3         0       chirp
         das 2.4375 2.981715                  2.375               4.275         4         1          0                    1         0       noise
         srp 2.3125 2.880430                  2.375               4.100         4         1          0                    1         0       noise
srp_neighbor 1.5000 2.121320                  1.000               3.100         4         1          0                    1         0       noise
         das 2.6875 2.896658                  2.625               3.850         4         0          0                    3         0       sweep
         srp 2.7500 2.984334                  2.625               4.025         4         0          0                    3         0       sweep
srp_neighbor 6.5625 7.257539                  6.125               9.975         4         0          0                    3         0       sweep
```

Flaga temporally_unstable oznacza odchylenie DOA ramek >10° w co najmniej jednej metodzie. Nie jest to skalibrowany przedział ufności. 8 z 12 pomiarów ma tę flagę.

We wszystkich plikach chirp/sweep wykryto ciągłą trajektorię lub stabilne stopnie częstotliwości. Decyzje selekcji zapisano niezależnie od referencji kątowej. Samo wykrycie pasma nie dowodzi, że każda wybrana ramka zawiera wyłącznie źródło docelowe; duża niestabilność czasowa pozostaje ostrzeżeniem.

Reszty fazy sąsiadów wg pasma (tylko prążki z ≥3 aktywnymi ramkami; phase_summary_by_frequency.csv):

```text
 low_hz  high_hz  weighted_phase_residual_rms_rad  weighted_coherence
    300      500                         0.271632            0.819317
    500     1000                         0.216827            0.914358
   1000     1500                         0.217817            0.910676
   1500     2000                         0.124497            0.951847
   2000     2500                         0.132929            0.982239
   2500     3000                         0.168346            0.966263
   3000     3500                         0.234527            0.959348
   3500     4000                         0.459340            0.927781
```

Zakres gęstości jedynek PDM: 0.497342–0.503600. Bitowo identyczne pary kanałów: 0. Nie dowodzi to poprawności geometrii ani synchronizacji akustycznej.

## Najważniejsze potwierdzone wnioski

DAS ma MAE 2.667°, SRP 120 par 2.646°, a SRP 15 sąsiadów 3.417°. Pełny SRP porównujemy z DAS na tych samych 12 nagraniach; niewielka różnica MAE nie dowodzi istotnej przewagi. Porównanie z sąsiadami i wszystkimi bazami dotyczy tego samego zbioru, bez wyboru bazy osobno dla każdego nagrania.

Największy błąd pełnego SRP: chirp_+60st_10m, oszacowanie 64.75°, referencja 60.00°. Ten przypadek pozostaje w metrykach ocenianego zbioru 12 nagrań. Wysokie lub jednoznaczne maksimum nie gwarantuje identyfikacji właściwego źródła.

Podejrzane poziomy/koherencja: noise_3_0st_10m: mic10 (-16.7 dB względem mediany), noise_3_0st_10m: mic15 (-12.7 dB względem mediany). Nie usuwano tych kanałów. Liczba powtórzeń flag jest widoczna w tabeli; pojedyncza flaga nie potwierdza trwałej usterki.

Błąd DAS nie rośnie monotonicznie z częstotliwością: istotne błędy występują również w dolnych pasmach, a zagregowane błędy w zakresie 2–3,5 kHz są mniejsze. Pasmo 3,5–4 kHz należy sprawdzać osobno z uwagi na niewielką liczbę ramek i aliasing długich par. Zależność czasu, SNR i składu nagrań nie pozwala przypisać całego trendu samej częstotliwości.

Hipotezy wymagające osobnej weryfikacji: odbicia lub obce źródła w fragmentach o odmiennym DOA, rozbieżność rzeczywistej geometrii/orientacji z modelem i niedokładna nominalna prędkość dźwięku. Reszty fazowe i systematyczne odchylenia kąta nie rozstrzygają pomiędzy tymi przyczynami. Nie zastosowano korekcji dopasowanej do referencji.

Zapis wykonania testów:

```text
...................................                                      [100%]
35 passed in 5.80s
```
