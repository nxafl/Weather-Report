# Python modules

The notebooks import the functions in this folder. Importing a module does not
download data or create files by itself.

## `config.py`

Contains the project settings:

- `CITIES`: six dictionaries containing name, slug and coordinates;
- `START_DATE` and `END_DATE`: study interval;
- `DAILY_VARIABLES`: Open-Meteo columns;
- `TIMEZONE`: API time zone.

## `data.py`

| Function | Purpose |
|---|---|
| `raw_file_path()` | Builds the standard city CSV path |
| `download_city_weather()` | Downloads and converts one Open-Meteo response |
| `download_all_cities()` | Downloads missing city files or reuses existing files |
| `load_raw_weather()` | Reads and combines the raw CSV files |
| `clean_weather_data()` | Parses dates and numeric weather columns |
| `validate_weather_data()` | Checks coverage, duplicates, missing values and physical consistency |
| `save_processed_data()` | Saves the validated daily table |

## `analysis.py`

| Function | Purpose |
|---|---|
| `add_calendar_features()` | Adds year, month, season and season year |
| `calculate_annual_summary()` | Calculates temperature, heat and precipitation indicators |
| `calculate_temperature_anomalies()` | Uses the 1961–1990 city baseline |
| `calculate_temperature_trends()` | Calculates descriptive NumPy slopes per decade |
| `calculate_seasonal_comparison()` | Compares complete seasons in two periods |
| `compare_climate_periods()` | Compares early and recent annual means |

## `plots.py`

Contains one style function, one save function and six plot functions. Every
plot has a title, labelled axes and units. Plotting functions return a
Matplotlib `Figure`, allowing the notebook to display and save the same figure.

## Example

```python
import pandas as pd

from scripts.analysis import (
    add_calendar_features,
    calculate_annual_summary,
    calculate_temperature_anomalies,
    calculate_temperature_trends,
)

weather = pd.read_csv(
    "data/processed/weather_daily_1940_2025.csv",
    parse_dates=["date"],
)
weather = add_calendar_features(weather)
annual = calculate_annual_summary(weather)
annual = calculate_temperature_anomalies(annual)
trends = calculate_temperature_trends(annual)
```
