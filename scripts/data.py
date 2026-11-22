"""Download, clean and validate daily Open-Meteo weather data."""

import time
from pathlib import Path

import pandas as pd
import requests

from scripts.config import DAILY_VARIABLES, END_DATE, START_DATE, TIMEZONE


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def raw_file_path(
    raw_directory: str | Path,
    city_slug: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Path:
    """Return the standard raw CSV path for one city and date interval."""
    filename = (
        f"{city_slug}_{start_date.replace('-', '')}_"
        f"{end_date.replace('-', '')}_era5.csv"
    )
    return Path(raw_directory) / filename


def download_city_weather(
    city: dict,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    max_retries: int = 3,
) -> pd.DataFrame:
    """Download daily ERA5 weather data for one city.

    Temporary server errors are retried. HTTP 429 waits one minute before a
    new attempt because it indicates that the API rate limit was reached.
    """
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative.")

    parameters = {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
        "models": "era5",
    }

    response = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(ARCHIVE_URL, params=parameters, timeout=60)
            if response.status_code == 429 and attempt < max_retries:
                print(f"Rate limit reached for {city['name']}; waiting 60 seconds...")
                time.sleep(60)
                continue
            response.raise_for_status()
            break
        except requests.RequestException as error:
            if attempt == max_retries:
                raise RuntimeError(
                    f"Download failed for {city['name']}: {error}"
                ) from error
            time.sleep(2 ** attempt)

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise RuntimeError(
            f"Open-Meteo returned invalid JSON for {city['name']}."
        ) from error
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise ValueError(f"Open-Meteo returned invalid daily data for {city['name']}.")

    expected_length = len(daily["time"])
    for variable in DAILY_VARIABLES:
        if variable not in daily or len(daily[variable]) != expected_length:
            raise ValueError(
                f"Open-Meteo returned an incomplete '{variable}' column for {city['name']}."
            )

    weather = pd.DataFrame({"time": daily["time"]})
    for variable in DAILY_VARIABLES:
        weather[variable] = daily[variable]

    weather.insert(0, "city_slug", city["slug"])
    weather.insert(0, "city", city["name"])
    weather["requested_latitude"] = city["latitude"]
    weather["requested_longitude"] = city["longitude"]
    weather["grid_latitude"] = payload.get("latitude")
    weather["grid_longitude"] = payload.get("longitude")
    weather["grid_elevation"] = payload.get("elevation")

    columns = [
        "city", "city_slug", "requested_latitude", "requested_longitude",
        "grid_latitude", "grid_longitude", "grid_elevation", "time",
        *DAILY_VARIABLES,
    ]
    return weather[columns]


def download_all_cities(
    cities: list[dict],
    raw_directory: str | Path,
    overwrite: bool = False,
) -> list[Path]:
    """Download every city and save one raw CSV file per city.

    Existing files are reused unless ``overwrite=True``. This avoids needless
    API calls and makes the notebook safe to run more than once.
    """
    raw_directory = Path(raw_directory)
    raw_directory.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for city in cities:
        path = raw_file_path(raw_directory, city["slug"])
        if path.exists() and not overwrite:
            print(f"Using existing file: {path.name}")
        else:
            print(f"Downloading {city['name']}...")
            weather = download_city_weather(city)
            weather.to_csv(path, index=False)
        saved_paths.append(path)
    return saved_paths


def load_raw_weather(file_paths: list[str | Path]) -> pd.DataFrame:
    """Load and combine raw city CSV files into one DataFrame."""
    frames = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Raw weather file not found: {path}")
        frames.append(pd.read_csv(path))
    if not frames:
        raise ValueError("No raw weather files were provided.")
    return pd.concat(frames, ignore_index=True)


def clean_weather_data(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Parse dates and numbers, then sort the daily weather observations."""
    required = {"city", "city_slug", "time", *DAILY_VARIABLES}
    missing = sorted(required - set(raw_data.columns))
    if missing:
        raise ValueError(f"Raw data is missing columns: {missing}.")

    weather = raw_data.copy().rename(columns={"time": "date"})
    weather["date"] = pd.to_datetime(weather["date"], errors="raise")
    for column in DAILY_VARIABLES:
        weather[column] = pd.to_numeric(weather[column], errors="coerce")
    return weather.sort_values(["city_slug", "date"]).reset_index(drop=True)


def validate_weather_data(
    weather: pd.DataFrame,
    city_slugs: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> pd.DataFrame:
    """Check coverage, duplicates, missing values and physical consistency.

    The only accepted missing value is precipitation on the first date of the
    study. The function raises ``ValueError`` for every other quality problem
    and returns a short city-level summary when all checks pass.
    """
    expected_dates = pd.date_range(start_date, end_date, freq="D")
    expected_cities = set(city_slugs)
    actual_cities = set(weather["city_slug"].dropna())
    if actual_cities != expected_cities:
        raise ValueError(
            f"Expected cities {sorted(expected_cities)}, found {sorted(actual_cities)}."
        )

    if weather.duplicated(["city_slug", "date"]).any():
        raise ValueError("Duplicate city-date observations were found.")

    if weather[["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min"]].isna().any().any():
        raise ValueError("Temperature columns contain missing values.")

    invalid_order = ~(
        (weather["temperature_2m_min"] <= weather["temperature_2m_mean"])
        & (weather["temperature_2m_mean"] <= weather["temperature_2m_max"])
    )
    if invalid_order.any():
        raise ValueError("Some rows do not satisfy minimum ≤ mean ≤ maximum temperature.")

    if (weather["precipitation_sum"].dropna() < 0).any():
        raise ValueError("Negative precipitation values were found.")

    missing_rain = weather.loc[weather["precipitation_sum"].isna(), "date"]
    allowed_missing_date = pd.Timestamp(start_date)
    if not missing_rain.empty and not missing_rain.eq(allowed_missing_date).all():
        raise ValueError("Unexpected missing precipitation values were found.")

    rows = []
    for city_slug in city_slugs:
        city_data = weather.loc[weather["city_slug"] == city_slug]
        actual_dates = pd.DatetimeIndex(city_data["date"])
        missing_dates = expected_dates.difference(actual_dates)
        if len(city_data) != len(expected_dates) or len(missing_dates) > 0:
            raise ValueError(f"Incomplete date coverage for {city_slug}.")
        rows.append(
            {
                "city_slug": city_slug,
                "rows": len(city_data),
                "first_date": city_data["date"].min(),
                "last_date": city_data["date"].max(),
                "missing_precipitation": int(city_data["precipitation_sum"].isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def save_processed_data(weather: pd.DataFrame, output_path: str | Path) -> Path:
    """Save the cleaned daily DataFrame to a CSV file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    return output_path
