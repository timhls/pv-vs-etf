# pv-vs-etf

Investitionsvergleichsrechner: **PV-Anlage vs. ETF** — inspiriert vom heise-Artikel
„PV-Anlage vs. ETF: Der Investitionsvergleichsrechner". Vergleicht eine Solar-Investition
(Dach-Anlage mit Einspeisung oder Balkonkraftwerk) mit der alternativen Anlage des gleichen
Kapitals in einen ETF — per **interner Zinsfuß (IRR)**, inkl. deutscher Steuerregeln und
Inflation der Strompreise.

## Features

- Zwei Szenarien: `rooftop` (Dach-Anlage, ggf. mit Batteriespeicher) und `balcony` (Balkonkraftwerk)
- IRR der PV-Cashflows vs. Netto-Rendite des ETF nach Steuern (Abgeltungsteuer, 30 % Teilfreistellung, Vorabpauschale, Sparerpauschbetrag)
- Amortisationszeit (einfach & kapitalwertbasiert), NPV der PV-Anlage diskontiert mit der ETF-Nettorendite
- Endvermögensvergleich: ETF-Einmalanlage vs. „PV + jährliche Ersparnisse in den ETF"
- Sensitivitäts-Heatmap: IRR über Strompreisanstieg × Eigenverbrauchsanteil
- Steuer-Presets: `s16_2025` (§ 16 EStG: bis 30 kWp steuerfrei) und `legacy_2023`
- Interaktiver HTML-Report (Plotly)

## Installation

```bash
cd pv-vs-etf
uv sync
```

## Verwendung

```bash
# Standard: 10-kWp-Dachanlage mit 10-kWh-Speicher, 25 Jahre
uv run pv-vs-etf

# Balkonkraftwerk-Szenario
uv run pv-vs-etf --mode balcony

# Mit HTML-Report + Sensitivitäts-Heatmap
uv run pv-vs-etf --report --sensitivity

# Eigene Parameter
uv run pv-vs-etf --kwp 12 --storage 8 --price 0.32 --price-growth 0.03 --etf-return 0.06 --years 20

# Komplette Konfigurationsdatei
cp config.example.toml config.toml
uv run pv-vs-etf --config config.toml --report
```

### Optionen

| Flag | Bedeutung |
|---|---|
| `--mode rooftop\|balcony` | Szenario (balcony setzt typische Defaults) |
| `--kwp` | Peakleistung in kWp |
| `--storage` | Speichergröße in kWh (0 = ohne) |
| `--price` | Strompreis EUR/kWh |
| `--price-growth` | Strompreisanstieg p.a. (0.03 = 3 %) |
| `--self-consumption` | Eigenverbrauchsanteil (0.3 = 30 %) |
| `--years` | Betrachtungshorizont (koppelt PV und ETF) |
| `--etf-return` | ETF-Bruttorendite p.a. |
| `--tax-preset` | `s16_2025` oder `legacy_2023` |
| `--report` | HTML-Report nach `output/report.html` |
| `--sensitivity` | IRR-Heatmap in den Report |

## Modell & Annahmen

### PV-Seite
- Investition Jahr 0: kWp × Kosten/kWp (+ Speicher × Kosten/kWh) − Förderung
- Erträge: spezifischer Ertrag × kWp, mit jährlicher Degradation (Default 0,5 %)
- Eigenverbrauchsanteil; Speicher erhöht ihn näherungsweise (Effekt ~ 35 % der Speicher-/Produktionsratio, gedeckelt bei 95 %)
- Ersparnis = selbst verbrauchte kWh × Strompreis (Strompreis steigt konfigurierbar p.a.)
- Einspeisevergütung nur im Rooftop-Modus (Default 7,8 ct/kWh, Teileinspeisung ≤ 10 kWp, Inbetriebnahme 2025)
- Laufende Kosten (Versicherung, Zählermiete, Wartung, +2 % p.a.), Wechselrichter-Tausch in Jahr 12
- Restwert optional am Ende der Laufzeit

### Steuern (PV)
- `s16_2025` (Default): § 16 EStG — Anlagen bis 30 kWp (bzw. 15 kWp je Gebäude bis 2024) sind
  einkommensteuerfrei; bei Optierung zur Kleinunternehmerregelung (§ 19 UStG, ab 2025 mit 0 %)
  entfällt die Umsammensatzsteuer. Preise als Nettopreise interpretiert, keine laufenden Steuern.
- `legacy_2023`: Einspeisevergütung steuerfrei; 70 % des Eigenverbrauchswerts gelten als
  Einnahme und werden mit dem persönlichen Steuersatz (Default 30 %) besteuert.

### ETF-Seite
- Rendite p.a. (Default 7 % nominal), davon 2 % Ausschüttungen; TER optional abzuziehen
- Jährliche **Vorabpauschale**: Basiszins × Jahresstartwert, 70 % davon steuerpflichtig,
  danach 30 % Teilfreistellung, Abgeltungsteuer 26,375 %; Sparerpauschbetrag (vereinfachend
  komplett im 1. Jahr)
- Am Horizontende: Abgeltungsteuer auf realisierte Gewinne nach 30 % Teilfreistellung

### Vergleichsmethodik
- **PV-IRR**: Zinssatz, der die PV-Cashflow-Reihe (Investition + N-Jahre Nettoeinnahmen) auf NPV 0 diskontiert
- **ETF-Nettorendite**: CAGR des ETF-Endwerts nach allen Steuern
- **Endvermögen**: (a) Kapital in ETF angelegt vs. (b) Kapital in PV, jährliche Netto-Cashflows in ETF (Sparplan)
- Hinweis: Risiko, Liquidität und Wertentwicklung sind nicht vergleichbar — der Vergleich ist
  rein monetär-modellhaft. Keine Steuer- oder Anlageberatung.

## Tests & Lint

```bash
uv run pytest
uv run ruff check .
```

## Struktur

```
src/pv_vs_etf/
├── model.py   # Konfiguration (dataclasses, TOML, Defaults)
├── pv.py      # PV-Cashflow-Modell (rooftop/balcony)
├── etf.py     # ETF-Projektion inkl. deutscher Steuerlogik
├── irr.py     # NPV/IRR/Amortisation (eigener Solver)
├── charts.py  # Plotly-Figuren + HTML-Report
└── cli.py     # Kommandozeile
```

## Haftungsausschluss

Vereinfachtes Rechenmodell zu Bildungszwecken. Keine Gewähr für Richtigkeit, Vollständigkeit
oder Aktualität — insbesondere der Steuertarife und Förderbedingungen. Keine Anlageberatung.
