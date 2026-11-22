"""Reusable utilities for the Weather Report notebooks.

The package contains the data models and Open-Meteo download functions used by
the project's notebooks. Importing the package never performs network requests.
"""

from scripts.cities import ITALIAN_CITIES, get_cities
from scripts.analysis import (
    MONTH_NAMES,
    SEASON_BY_MONTH,
    add_annual_temperature_anomalies,
    add_calendar_features,
    calculate_annual_indicators,
    calculate_heatwave_indicators,
    calculate_monthly_climatology,
    calculate_monthly_summary,
    calculate_monthly_temperature_anomalies,
    compare_climate_periods,
    estimate_temperature_trends,
    merge_annual_indicators,
)
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
from scripts.visualization import (
    CITY_COLORS,
    configure_plot_style,
    plot_annual_temperature,
    plot_annual_temperature_anomalies,
    plot_extreme_heat_indicators,
    plot_monthly_anomaly_heatmaps,
    plot_monthly_climatology,
    plot_precipitation_indicators,
    plot_temperature_distributions,
    plot_temperature_trends,
    save_figure,
)

__all__ = [
    "DEFAULT_DAILY_VARIABLES",
    "ITALIAN_CITIES",
    "MONTH_NAMES",
    "SEASON_BY_MONTH",
    "CITY_COLORS",
    "ArchiveRequest",
    "City",
    "DataQualityReport",
    "OpenMeteoError",
    "WeatherDataset",
    "add_annual_temperature_anomalies",
    "add_calendar_features",
    "build_archive_url",
    "build_quality_report",
    "calculate_annual_indicators",
    "calculate_heatwave_indicators",
    "calculate_monthly_climatology",
    "calculate_monthly_summary",
    "calculate_monthly_temperature_anomalies",
    "compare_climate_periods",
    "clean_weather_data",
    "configure_plot_style",
    "discover_raw_csv_files",
    "fetch_city_weather",
    "fetch_multiple_cities",
    "estimate_temperature_trends",
    "get_cities",
    "load_raw_weather_csvs",
    "merge_annual_indicators",
    "plot_annual_temperature",
    "plot_annual_temperature_anomalies",
    "plot_extreme_heat_indicators",
    "plot_monthly_anomaly_heatmaps",
    "plot_monthly_climatology",
    "plot_precipitation_indicators",
    "plot_temperature_distributions",
    "plot_temperature_trends",
    "save_records_csv",
    "save_processed_csv",
    "save_figure",
    "save_response_json",
]
