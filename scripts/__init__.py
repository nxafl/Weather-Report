"""Reusable utilities for the Weather Report notebooks.

The package contains the data models and Open-Meteo download functions used by
the project's notebooks. Importing the package never performs network requests.
"""

from scripts.cities import ITALIAN_CITIES, get_cities
from scripts.models import (
    DEFAULT_DAILY_VARIABLES,
    ArchiveRequest,
    City,
    WeatherDataset,
)
from scripts.open_meteo import (
    OpenMeteoError,
    build_archive_url,
    fetch_city_weather,
    fetch_multiple_cities,
    save_records_csv,
    save_response_json,
)
from scripts.preprocessing import (
    DataQualityReport,
    build_quality_report,
    clean_weather_data,
    discover_raw_csv_files,
    load_raw_weather_csvs,
    save_processed_csv,
)

__all__ = [
    "DEFAULT_DAILY_VARIABLES",
    "ITALIAN_CITIES",
    "ArchiveRequest",
    "City",
    "DataQualityReport",
    "OpenMeteoError",
    "WeatherDataset",
    "build_archive_url",
    "build_quality_report",
    "clean_weather_data",
    "discover_raw_csv_files",
    "fetch_city_weather",
    "fetch_multiple_cities",
    "get_cities",
    "load_raw_weather_csvs",
    "save_records_csv",
    "save_processed_csv",
    "save_response_json",
]
