# Weather Report: Climate Change in Italian Cities

**Aruzhan Bolatova - Student ID: 90402A**

## Project overview

This project investigates how climate conditions have changed across
six Italian cities between 1940 and 2025. It uses daily historical weather data
from the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
and the ERA5 reanalysis model.

The complete Python workflow covers:

- data acquisition through a public API;
- validation and reproducible preprocessing;
- exploratory data analysis;
- temperature anomalies and climate normals;
- heatwave and extreme-weather indicators;
- annual and seasonal trend estimation;
- confidence intervals and robust covariance estimates;
- comparisons between cities;
- separate analyses of rainfall amount, frequency and intensity.


## Research questions

The project examines the following questions:

1. Have annual mean temperatures increased since 1940?
2. Which cities have warmed most rapidly?
3. Does the warming rate differ between seasons?
4. Are minimum and maximum temperatures changing at the same rate?
5. Have hot days, tropical nights and heatwaves become more frequent?
6. Are city-level warming trends statistically different?
7. Have rainfall amount, frequency or intensity changed over time?

## Study area and data

| City | Area represented |
|---|---|
| Milan | Northern Italy and the Po Valley |
| Turin | Northwestern Italy and Alpine influence |
| Rome | Central Italy |
| Bari | Southern Adriatic coast |
| Palermo | Southern Mediterranean climate |
| Cagliari | Insular and maritime climate |

The dataset contains daily observations from **1 January 1940 through 31
December 2025** for:

- mean temperature at 2 metres;
- maximum temperature at 2 metres;
- minimum temperature at 2 metres;
- total precipitation.

ERA5 is used consistently across the entire period. The incomplete year 2026 is
not included in annual comparisons.

## Repository structure

```text
Weather-Report/
├── README.md
├── LICENSE
├── requirements.txt
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_data_cleaning.ipynb
│   └── 03_exploratory_data_analysis.ipynb
├── scripts/
│   ├── __init__.py
│   ├── analysis.py
│   ├── cities.py
│   ├── models.py
│   ├── open_meteo.py
│   ├── preprocessing.py
│   ├── statistical_analysis.py
│   ├── visualization.py
│   └── README.md
├── tests/
│   ├── test_analysis.py
│   ├── test_preprocessing.py
│   ├── test_statistical_analysis.py
│   └── test_weather_models.py
├── data/                    # Generated locally and ignored by Git
│   ├── raw/
│   └── processed/
└── reports/
    └── figures/             # Generated locally and ignored by Git
```

### Main modules

| File | Responsibility |
|---|---|
| `scripts/models.py` | Validated city, API-request and weather-response models |
| `scripts/cities.py` | Coordinates and metadata for the six cities |
| `scripts/open_meteo.py` | API requests, retry handling and JSON/CSV serialization |
| `scripts/preprocessing.py` | Loading, cleaning and data-quality validation |
| `scripts/analysis.py` | Climate features, anomalies and annual/monthly indicators |
| `scripts/statistical_analysis.py` | Regressions, confidence intervals and interaction models |
| `scripts/visualization.py` | Reusable project charts and figure export |

The functions contain type hints and docstrings. Additional usage examples are
available in [`scripts/README.md`](scripts/README.md).

## Installation

Python **3.11 or newer** is recommended.

### 1. Clone or download the repository

```bash
git clone <repository-url>
cd Weather-Report
```

If the repository is already available locally, open a terminal in its root
directory.

### 2. Create a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

The terminal prompt should display `(.venv)` after activation.

### 3. Install the dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start JupyterLab

```bash
python -m jupyter lab
```

Because JupyterLab is started from the activated virtual environment, its
Python kernel should already use the installed project dependencies.

If an IDE does not detect the environment automatically, register it manually:

```bash
python -m ipykernel install --user \
  --name weather-report \
  --display-name "Python (Weather Report)"
```

Then select **Python (Weather Report)** as the notebook kernel.

## Running the project

Run the notebooks in numerical order. Each notebook depends on files produced
by the previous one.

### 1. Data collection

Open and run:

```text
notebooks/01_data_collection.ipynb
```

This notebook:

- downloads daily ERA5 data for all six cities;
- retries temporary API errors automatically;
- waits before retrying if Open-Meteo returns HTTP 429;
- stores the original API responses as JSON;
- stores normalized daily observations as CSV;
- verifies the expected number of rows.

Generated files are written to:

```text
data/raw/
```

The complete download can take several minutes because Open-Meteo applies
request limits to long historical queries. Do not interrupt a cell while it is
waiting to retry.

### 2. Data cleaning and validation

Open and run:

```text
notebooks/02_data_cleaning.ipynb
```

This notebook:

- combines the six raw CSV files;
- parses and standardizes columns;
- checks missing and duplicate dates;
- verifies temperature ordering;
- checks negative precipitation values;
- validates complete city-level coverage;
- writes one analysis-ready daily dataset.

Main output:

```text
data/processed/weather_daily_1940_2025.csv
```

The validated dataset contains **188,472 observations**, or **31,412 daily
records per city**.

### 3. Exploratory and statistical analysis

Open and run:

```text
notebooks/03_exploratory_data_analysis.ipynb
```

This notebook produces:

- daily temperature distributions;
- 1961–1990 monthly climate normals;
- annual temperatures and 10-year rolling averages;
- annual anomaly plots;
- monthly anomaly heatmaps;
- city-specific heatwave thresholds;
- hot-day and tropical-night indicators;
- annual trends with 95% confidence intervals;
- seasonal temperature trends;
- minimum-versus-maximum temperature trends;
- a city-by-year interaction model;
- trends in extreme-heat indicators;
- separate rainfall amount, frequency and intensity trends;
- early-versus-recent climate comparisons.

Derived tables are stored in `data/processed/`. Figures are stored in:

```text
reports/figures/eda/
```

## Testing

With the virtual environment activated, run:

```bash
python -m unittest discover -s tests -v
```

The test suite covers:

- API-request construction and response validation;
- rate-limit retry behavior;
- data-quality policies;
- calendar and climate feature engineering;
- annual precipitation completeness;
- heatwave identification;
- trend units and confidence models;
- seasonal aggregation;
- city-by-year interaction slopes.

## Methodology

### Climate reference period

Temperature anomalies use **1961–1990** as a fixed reference period. Monthly
anomalies compare each month with the same calendar month in the baseline, so
normal seasonality is removed.

### Heat indicators

- **Hot day:** maximum temperature of at least 30 °C.
- **Very hot day:** maximum temperature of at least 35 °C.
- **Tropical night:** minimum temperature of at least 20 °C.
- **Heatwave:** at least three consecutive summer days at or above the city's
  90th percentile of summer maximum temperature during 1961–1990.

### Statistical models

- Individual annual and seasonal trends use ordinary least squares.
- Confidence intervals use Newey–West HAC covariance with one lag.
- The pooled city-by-year model uses HC3 robust covariance.
- Slopes are reported per decade rather than per year.
- Rainfall is analysed separately as amount, frequency and intensity.

Statistical significance is not treated as proof of causation. Effect sizes,
confidence intervals and dataset limitations must be considered together.

## Main findings

The exploratory annual temperature trends are approximately:

| City | Temperature trend |
|---|---:|
| Milan | +0.37 °C per decade |
| Turin | +0.37 °C per decade |
| Palermo | +0.27 °C per decade |
| Rome | +0.23 °C per decade |
| Cagliari | +0.21 °C per decade |
| Bari | +0.19 °C per decade |

All annual temperature confidence intervals are above zero. The city-by-year
model does not distinguish Turin's warming rate from Milan's, while Bari,
Cagliari, Palermo and Rome show slower trends than Milan.

Temperature trends vary by season and between daily minimum and maximum
temperature. Several hot-day, tropical-night and heatwave indicators increase
over time. Annual precipitation totals do not show a uniform significant trend,
but frequency and intensity indicators reveal local changes that annual totals
alone would hide.

## Data-quality notes

- Open-Meteo returns one missing precipitation value on 1 January 1940 for
  every city.
- These six values remain missing and are never replaced with invented values.
- Precipitation indicators for 1940 are therefore excluded from annual trend
  models.
- ERA5 represents a model grid cell around each city, not a single urban weather
  station.

## Limitations

- The analysis cannot fully separate regional climate change from urban
  heat-island effects.
- ERA5 spatial resolution limits interpretation of highly localized rainfall
  events.
- Linear trends summarize long-term direction but do not capture every form of
  nonlinear climate variability.
- Regression results quantify associations with time; they do not perform
  causal attribution.

## Reproducibility

Raw data, processed data and figures are intentionally excluded from Git because
they are generated artifacts. They can be reproduced by running the three
notebooks in order.

The API responses, source-file names, selected ERA5 model, coordinates, units,
date interval and baseline assumptions are retained throughout the workflow.

## License

See [`LICENSE`](LICENSE) for repository licensing information.
