# Weather download scripts

The modules in this directory are designed to be imported by the project
notebooks. Importing them does not download or write any data.

## Download one city

```python
from scripts import ITALIAN_CITIES, fetch_city_weather

milan = fetch_city_weather(ITALIAN_CITIES["milan"])
print(f"Downloaded {len(milan):,} daily observations")
```

The default period is 1 January 1940 through 31 December 2025. The selected
model is always ERA5.

Long historical requests can reach Open-Meteo's per-minute usage limit. When
the API returns HTTP 429, the downloader waits for the next minute window and
retries automatically. A warning is displayed in the notebook while it waits;
the cell should not be interrupted during that pause.

## Create a pandas DataFrame

```python
import pandas as pd

milan_df = pd.DataFrame(milan.iter_records())
milan_df.head()
```

## Download selected cities

```python
from scripts import fetch_multiple_cities, get_cities

cities = get_cities(["milan", "rome", "palermo"])
datasets = fetch_multiple_cities(cities)

weather_df = pd.concat(
    [pd.DataFrame(dataset.iter_records()) for dataset in datasets.values()],
    ignore_index=True,
)
```

## Save raw and tabular data

Saving is explicit, so a notebook can inspect the response before writing it.
Existing files are protected unless `overwrite=True` is passed.

```python
from scripts import save_records_csv, save_response_json

save_response_json(milan, "data/raw/milan_1940_2025.json")
save_records_csv(milan, "data/raw/milan_1940_2025.csv")
```

The JSON file preserves the complete API response. The CSV file contains one
row per day and includes the city name, requested coordinates, grid-cell
coordinates, elevation and the requested weather variables.

## Clean and validate the raw files

The second notebook uses the preprocessing functions to discover the six CSV
files, combine them and build a detailed quality report before saving anything.

```python
from datetime import date
from scripts import (
    build_quality_report,
    clean_weather_data,
    discover_raw_csv_files,
    get_cities,
    load_raw_weather_csvs,
)

cities = get_cities()
paths = discover_raw_csv_files("data/raw", [city.slug for city in cities])
weather = clean_weather_data(load_raw_weather_csvs(paths))
report = build_quality_report(
    weather,
    expected_city_slugs=[city.slug for city in cities],
    start_date=date(1940, 1, 1),
    end_date=date(2025, 12, 31),
    allowed_missing_values={"precipitation_sum": {date(1940, 1, 1)}},
)

print(report.issue_counts)
print(report.is_valid)
```

At the beginning of the ERA5 archive, Open-Meteo returns no daily precipitation
value for 1 January 1940 in any of the six city responses. The cleaning notebook
keeps those six boundary values missing, reports them as an explicit allowed
exception and does not invent replacement values.

## Download a short period while developing

Use a small date range when testing a notebook to avoid repeatedly requesting
the full historical series.

```python
from datetime import date

sample = fetch_city_weather(
    ITALIAN_CITIES["rome"],
    start_date=date(2020, 1, 1),
    end_date=date(2020, 1, 31),
)
```
