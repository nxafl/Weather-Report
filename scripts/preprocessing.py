"""Loading, cleaning and quality checks for raw Open-Meteo CSV files.

The functions in this module are designed for notebook use. Pandas is imported
only when one of the data-processing functions is called, so the lightweight
download utilities remain usable without the analysis dependencies installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "city",
    "city_slug",
    "requested_latitude",
    "requested_longitude",
    "grid_latitude",
    "grid_longitude",
    "grid_elevation",
)
"""Location and grid metadata expected in every normalized raw CSV."""

WEATHER_COLUMNS: tuple[str, ...] = (
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
)
"""Core weather measurements required by the project plan."""

RAW_REQUIRED_COLUMNS: tuple[str, ...] = (
    *IDENTIFIER_COLUMNS,
    "time",
    *WEATHER_COLUMNS,
)
"""Columns that must be present before raw files can be combined."""


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Results of the structural and physical data-quality checks.

    Attributes
    ----------
    city_summary:
        DataFrame with row counts, date bounds and completeness by city.
    duplicate_rows:
        Rows belonging to duplicate ``city_slug`` and ``date`` keys.
    invalid_temperature_rows:
        Complete rows that violate ``minimum <= mean <= maximum``.
    negative_precipitation_rows:
        Rows containing a precipitation total below zero.
    out_of_range_rows:
        Rows dated outside the requested analysis period.
    missing_dates:
        DataFrame containing every absent city-date combination.
    null_counts:
        Unexpected missing-value counts for the columns required for analysis.
    allowed_null_counts:
        Missing values explicitly accepted by the documented cleaning policy.
    unexpected_cities:
        City slugs present in the data but absent from the expected catalogue.
    """

    city_summary: Any
    duplicate_rows: Any
    invalid_temperature_rows: Any
    negative_precipitation_rows: Any
    out_of_range_rows: Any
    missing_dates: Any
    null_counts: dict[str, int]
    allowed_null_counts: dict[str, int]
    unexpected_cities: tuple[str, ...]

    @property
    def issue_counts(self) -> dict[str, int]:
        """Return a compact mapping of check names to detected issue counts."""
        return {
            "duplicate_rows": len(self.duplicate_rows),
            "invalid_temperature_rows": len(self.invalid_temperature_rows),
            "negative_precipitation_rows": len(self.negative_precipitation_rows),
            "out_of_range_rows": len(self.out_of_range_rows),
            "missing_dates": len(self.missing_dates),
            "unexpected_null_values": sum(self.null_counts.values()),
            "unexpected_cities": len(self.unexpected_cities),
        }

    @property
    def is_valid(self) -> bool:
        """Return ``True`` only when every mandatory quality check passes."""
        issue_free = all(count == 0 for count in self.issue_counts.values())
        complete_cities = bool(
            len(self.city_summary) > 0 and self.city_summary["is_complete"].all()
        )
        return issue_free and complete_cities


def discover_raw_csv_files(
    raw_directory: str | Path,
    expected_city_slugs: Iterable[str],
) -> list[Path]:
    """Locate exactly one ERA5 CSV file for each expected city.

    Parameters
    ----------
    raw_directory:
        Directory populated by the data-collection notebook.
    expected_city_slugs:
        City identifiers in the desired output order.

    Returns
    -------
    list of pathlib.Path
        CSV paths ordered like ``expected_city_slugs``.

    Raises
    ------
    FileNotFoundError
        If the directory or a city's CSV file is missing.
    ValueError
        If a city has more than one matching ERA5 CSV file or city slugs are
        duplicated.
    """
    directory = Path(raw_directory).expanduser().resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Raw data directory does not exist: {directory}")

    city_slugs = list(expected_city_slugs)
    if not city_slugs:
        raise ValueError("At least one expected city slug is required.")
    if len(city_slugs) != len(set(city_slugs)):
        raise ValueError("Expected city slugs must be unique.")

    discovered: list[Path] = []
    for city_slug in city_slugs:
        matches = sorted(directory.glob(f"{city_slug}_*_era5.csv"))
        if not matches:
            raise FileNotFoundError(
                f"No ERA5 CSV file found for city '{city_slug}' in {directory}."
            )
        if len(matches) > 1:
            names = ", ".join(path.name for path in matches)
            raise ValueError(
                f"Multiple ERA5 CSV files found for city '{city_slug}': {names}."
            )
        discovered.append(matches[0])
    return discovered


def load_raw_weather_csvs(file_paths: Iterable[str | Path]) -> Any:
    """Load and combine normalized raw CSV files into one DataFrame.

    Parameters
    ----------
    file_paths:
        Iterable of CSV files created by ``save_records_csv``.

    Returns
    -------
    pandas.DataFrame
        Combined raw observations with an additional ``source_file`` column.

    Raises
    ------
    ValueError
        If no paths are supplied or a file is missing required columns.
    FileNotFoundError
        If one of the supplied paths does not exist.
    ModuleNotFoundError
        If pandas is not installed.
    """
    pd = _require_pandas()
    paths = [Path(path).expanduser().resolve() for path in file_paths]
    if not paths:
        raise ValueError("At least one raw CSV file is required.")

    dataframes = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Raw CSV file does not exist: {path}")
        dataframe = pd.read_csv(path)
        missing_columns = sorted(set(RAW_REQUIRED_COLUMNS) - set(dataframe.columns))
        if missing_columns:
            raise ValueError(
                f"Raw file '{path.name}' is missing columns: {missing_columns}."
            )
        dataframe["source_file"] = path.name
        dataframes.append(dataframe)

    return pd.concat(dataframes, ignore_index=True, sort=False)


def clean_weather_data(raw_data: Any) -> Any:
    """Standardize column names, types and row ordering without dropping data.

    Parameters
    ----------
    raw_data:
        DataFrame returned by :func:`load_raw_weather_csvs`.

    Returns
    -------
    pandas.DataFrame
        Copy with ``time`` renamed to ``date``, parsed dates, numeric weather
        columns, string city identifiers and deterministic city-date ordering.

    Notes
    -----
    Invalid numeric values become missing values so that
    :func:`build_quality_report` can expose them. This function deliberately
    does not delete duplicates, invalid measurements or incomplete rows.
    """
    pd = _require_pandas()
    data = raw_data.copy()
    if "time" not in data.columns:
        raise ValueError("Input data must contain the raw 'time' column.")
    if "date" in data.columns:
        raise ValueError("Input data cannot contain both 'time' and 'date'.")

    data = data.rename(columns={"time": "date"})
    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    numeric_columns = (*IDENTIFIER_COLUMNS[2:], *WEATHER_COLUMNS)
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["city"] = data["city"].astype("string").str.strip()
    data["city_slug"] = data["city_slug"].astype("string").str.strip()
    return data.sort_values(
        ["city_slug", "date"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)


def build_quality_report(
    data: Any,
    expected_city_slugs: Sequence[str],
    start_date: date,
    end_date: date,
    *,
    allowed_missing_values: Mapping[str, Iterable[date]] | None = None,
) -> DataQualityReport:
    """Run completeness and physical-consistency checks on cleaned data.

    Parameters
    ----------
    data:
        Cleaned DataFrame returned by :func:`clean_weather_data`.
    expected_city_slugs:
        Complete list of city identifiers that should be present.
    start_date, end_date:
        Inclusive date range expected for every city.
    allowed_missing_values:
        Optional mapping from column names to dates on which missing values are
        known and explicitly accepted. Allowed values remain missing in the
        data and are reported separately; they are never filled or removed.

    Returns
    -------
    DataQualityReport
        Detailed issue tables, per-city summary and overall validity status.

    Raises
    ------
    ValueError
        If the date range, expected cities or required cleaned columns are
        invalid.
    """
    pd = _require_pandas()
    if end_date < start_date:
        raise ValueError("end_date cannot precede start_date.")

    city_slugs = list(expected_city_slugs)
    if not city_slugs or len(city_slugs) != len(set(city_slugs)):
        raise ValueError("Expected city slugs must be a non-empty unique sequence.")

    required_columns = {
        "city",
        "city_slug",
        "date",
        *IDENTIFIER_COLUMNS[2:],
        *WEATHER_COLUMNS,
    }
    missing_columns = sorted(required_columns - set(data.columns))
    if missing_columns:
        raise ValueError(f"Cleaned data is missing columns: {missing_columns}.")

    allowed_missing_values = allowed_missing_values or {}
    unknown_allowed_columns = sorted(set(allowed_missing_values) - required_columns)
    if unknown_allowed_columns:
        raise ValueError(
            "Allowed missing-value policy references unknown columns: "
            f"{unknown_allowed_columns}."
        )

    expected_dates = pd.date_range(start=start_date, end=end_date, freq="D")
    start_timestamp = pd.Timestamp(start_date)
    end_timestamp = pd.Timestamp(end_date)

    duplicate_mask = data.duplicated(["city_slug", "date"], keep=False)
    duplicate_rows = data.loc[duplicate_mask].copy()

    complete_temperatures = data[list(WEATHER_COLUMNS[:3])].notna().all(axis=1)
    ordered_temperatures = (
        (data["temperature_2m_min"] <= data["temperature_2m_mean"])
        & (data["temperature_2m_mean"] <= data["temperature_2m_max"])
    )
    invalid_temperature_rows = data.loc[
        complete_temperatures & ~ordered_temperatures
    ].copy()
    negative_precipitation_rows = data.loc[data["precipitation_sum"] < 0].copy()
    out_of_range_rows = data.loc[
        data["date"].notna()
        & ~data["date"].between(start_timestamp, end_timestamp, inclusive="both")
    ].copy()

    analysis_columns = ("city", "city_slug", "date", *WEATHER_COLUMNS)
    unexpected_null_masks: dict[str, Any] = {}
    allowed_null_counts: dict[str, int] = {}
    null_counts: dict[str, int] = {}
    for column in analysis_columns:
        null_mask = data[column].isna()
        allowed_dates = pd.DatetimeIndex(
            pd.to_datetime(list(allowed_missing_values.get(column, ())))
        )
        allowed_mask = (
            null_mask & data["date"].isin(allowed_dates)
            if len(allowed_dates) > 0
            else pd.Series(False, index=data.index)
        )
        unexpected_null_masks[column] = null_mask & ~allowed_mask
        allowed_null_counts[column] = int(allowed_mask.sum())
        null_counts[column] = int(unexpected_null_masks[column].sum())

    actual_cities = set(data["city_slug"].dropna().astype(str).unique())
    unexpected_cities = tuple(sorted(actual_cities - set(city_slugs)))
    city_summaries: list[dict[str, Any]] = []
    missing_date_records: list[dict[str, Any]] = []

    for city_slug in city_slugs:
        city_data = data.loc[data["city_slug"] == city_slug]
        valid_dates = pd.DatetimeIndex(city_data["date"].dropna().unique())
        missing_city_dates = expected_dates.difference(valid_dates)
        missing_date_records.extend(
            {"city_slug": city_slug, "date": missing_date}
            for missing_date in missing_city_dates
        )

        duplicate_date_count = int(city_data.duplicated("date", keep=False).sum())
        city_index = city_data.index
        city_unexpected_null_count = sum(
            int(unexpected_null_masks[column].loc[city_index].sum())
            for column in WEATHER_COLUMNS
        )
        city_allowed_null_count = sum(
            int(city_data[column].isna().sum())
            - int(unexpected_null_masks[column].loc[city_index].sum())
            for column in WEATHER_COLUMNS
        )
        city_summaries.append(
            {
                "city_slug": city_slug,
                "row_count": len(city_data),
                "expected_rows": len(expected_dates),
                "first_date": city_data["date"].min(),
                "last_date": city_data["date"].max(),
                "missing_dates": len(missing_city_dates),
                "duplicate_rows": duplicate_date_count,
                "unexpected_missing_values": city_unexpected_null_count,
                "allowed_missing_values": city_allowed_null_count,
                "is_complete": (
                    len(city_data) == len(expected_dates)
                    and len(missing_city_dates) == 0
                    and duplicate_date_count == 0
                    and city_unexpected_null_count == 0
                ),
            }
        )

    city_summary = pd.DataFrame(city_summaries)
    missing_dates = pd.DataFrame(
        missing_date_records,
        columns=["city_slug", "date"],
    )
    return DataQualityReport(
        city_summary=city_summary,
        duplicate_rows=duplicate_rows,
        invalid_temperature_rows=invalid_temperature_rows,
        negative_precipitation_rows=negative_precipitation_rows,
        out_of_range_rows=out_of_range_rows,
        missing_dates=missing_dates,
        null_counts=null_counts,
        allowed_null_counts=allowed_null_counts,
        unexpected_cities=unexpected_cities,
    )


def save_processed_csv(
    data: Any,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Save a cleaned DataFrame to CSV using an atomic file replacement.

    Parameters
    ----------
    data:
        Cleaned and validated pandas DataFrame.
    path:
        Destination path. Missing parent directories are created.
    overwrite:
        When ``False`` (default), refuse to replace an existing dataset.

    Returns
    -------
    pathlib.Path
        Resolved path of the saved CSV file.

    Raises
    ------
    FileExistsError
        If the destination exists and ``overwrite`` is false.
    """
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Processed file already exists: {destination}. "
            "Pass overwrite=True only when regeneration is intentional."
        )

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        data.to_csv(temporary, index=False, date_format="%Y-%m-%d")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _require_pandas() -> Any:
    """Import pandas or raise an installation message tailored to the project."""
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "pandas is required for preprocessing. Install the project "
            "dependencies from requirements.txt before running this notebook."
        ) from exc
    return pd
