# Weather Report: Climate Change in Italian Cities

**Aruzhan Bolatova - Student ID: 90402A**

## Project objective

This Python project investigates how weather and climate indicators changed in
six Italian cities between 1940 and 2025. It uses daily historical data from
the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
and its ERA5 reanalysis dataset.

The analysis answers five questions:

1. How has annual mean temperature changed?
2. Which cities have the largest descriptive warming trends?
3. Have hot days and tropical nights become more frequent?
4. How have annual precipitation patterns changed?
5. How do recent seasonal temperatures compare with the historical period?


## Study area and data

The selected cities represent different parts of Italy:

| City | Area |
|---|---|
| Milan | Northern Italy and the Po Valley |
| Turin | Northwestern Italy and Alpine influence |
| Rome | Central Italy |
| Bari | Southern Adriatic coast |
| Palermo | Southern Mediterranean climate |
| Cagliari | Insular and maritime climate |

The daily variables are:

- mean temperature at 2 metres, in °C;
- maximum temperature at 2 metres, in °C;
- minimum temperature at 2 metres, in °C;
- daily precipitation, in mm.

The processed dataset contains 188,472 rows: 31,412 daily observations for
each city from 1 January 1940 to 31 December 2025.

## Repository structure

```text
Weather-Report/
├── notebooks/
│   ├── 01_prepare_data.ipynb
│   └── 02_climate_analysis.ipynb
├── scripts/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── analysis.py
│   ├── plots.py
│   └── README.md
├── tests/
│   ├── test_data.py
│   └── test_analysis.py
├── data/                  # Generated locally and ignored by Git
│   ├── raw/
│   └── processed/
├── reports/               # Generated figures, ignored by Git
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

### Python modules

| File | Purpose |
|---|---|
| `scripts/config.py` | Cities, dates and Open-Meteo variables |
| `scripts/data.py` | API download, CSV loading, cleaning and validation |
| `scripts/analysis.py` | Annual summaries, anomalies, trends and period comparisons |
| `scripts/plots.py` | Six reusable climate visualizations |

Every public function has a short docstring. The notebooks import these
functions instead of duplicating their logic.

## Installation

Python 3.11 or newer is recommended.

### 1. Open the project

```bash
git clone <repository-url>
cd Weather-Report
```

### 2. Create a virtual environment

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install the libraries

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start JupyterLab

```bash
jupyter lab
```

## Running the project

Run the notebooks in order.

### Notebook 1: prepare data

Open `notebooks/01_prepare_data.ipynb` and run all cells.

The notebook:

- downloads one raw CSV for each city;
- reuses existing CSV files to avoid unnecessary API calls;
- waits and retries after HTTP 429 rate-limit responses;
- combines the six files with pandas;
- parses dates and numeric values;
- checks city and date coverage;
- checks duplicate rows and missing values;
- verifies `minimum ≤ mean ≤ maximum` temperature;
- rejects negative precipitation;
- saves `data/processed/weather_daily_1940_2025.csv`.

The first full download can take several minutes. If Open-Meteo reaches its
request limit, the downloader waits one minute before trying again.

### Notebook 2: climate analysis

Open `notebooks/02_climate_analysis.ipynb` and run all cells.

The notebook calculates descriptive statistics and produces six figures:

1. annual mean temperature and 10-year averages;
2. annual temperature anomalies;
3. descriptive temperature trends by city;
4. hot days and tropical nights;
5. annual precipitation totals;
6. seasonal historical-versus-recent temperatures.

Figures are saved in `reports/figures/eda/`.

## Methods

### Temperature anomalies

The reference period is 1961–1990. Each city's anomaly is:

```text
annual temperature - that city's 1961–1990 mean temperature
```

An anomaly above zero is warmer than the reference average. An anomaly below
zero is colder.

### Event indicators

- Hot day: maximum temperature ≥ 30 °C.
- Tropical night: minimum temperature ≥ 20 °C.
- Heavy-rain day: precipitation ≥ 20 mm.

These fixed definitions are transparent and reproducible. They represent
different levels of rarity in cities with different local climates.

### Descriptive linear trend

`numpy.polyfit()` fits a straight line to annual mean temperature. The slope is
multiplied by ten and reported in °C per decade.

The slope summarizes the average observed direction. It is not a statistical
significance test and does not prove causation.

### Period and seasonal comparisons

The project compares two complete 30-year periods:

- historical: 1941–1970;
- recent: 1996–2025.

Meteorological seasons are winter (December–February), spring (March–May),
summer (June–August) and autumn (September–November). December belongs to the
following winter year. Incomplete boundary seasons are excluded.

## Descriptive results

The linear temperature slopes calculated from the current dataset are:

| City | °C per decade |
|---|---:|
| Milan | +0.37 |
| Turin | +0.37 |
| Palermo | +0.27 |
| Rome | +0.23 |
| Cagliari | +0.21 |
| Bari | +0.19 |

All six recent-period temperature means are higher than their historical-period
means. The differences range from approximately +1.38 °C in Bari to +2.63 °C
in Milan.

The average annual number of hot days is also higher in the recent period for
all cities. The largest descriptive increases are approximately 27 additional
days in Milan and 26 in Turin.

Precipitation is much more variable. The period differences are comparatively
small and do not form one consistent direction across all six cities. These are
descriptive observations, not claims of statistical significance.

## Data-quality decisions

- Open-Meteo returns one missing precipitation value on 1 January 1940 for
  every city.
- These six missing values remain missing; they are never replaced with zero.
- Annual precipitation for 1940 is therefore left missing.
- Temperature comparisons use the same years for every city.
- API failures stop the pipeline with a readable error instead of silently
  producing partial data.

## Libraries

- `pandas`: loading, cleaning, grouping and aggregation;
- `numpy`: descriptive linear trends;
- `requests`: Open-Meteo HTTP requests;
- `matplotlib` and `seaborn`: visualization;
- `jupyterlab`: notebook execution and presentation.

## License

See [`LICENSE`](LICENSE).
