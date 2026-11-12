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

__all__ = [
    "DEFAULT_DAILY_VARIABLES",
    "ITALIAN_CITIES",
    "ArchiveRequest",
    "City",
    "OpenMeteoError",
    "WeatherDataset",
    "build_archive_url",
    "fetch_city_weather",
    "fetch_multiple_cities",
    "get_cities",
    "save_records_csv",
    "save_response_json",
]
