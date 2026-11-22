"""Simple pandas and NumPy calculations used in the climate notebook."""

from collections.abc import Iterable

import numpy as np
import pandas as pd


SEASON_BY_MONTH = {
    12: "Winter",
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Autumn",
    10: "Autumn",
    11: "Autumn",
}

DAILY_COLUMNS = (
    "city",
    "city_slug",
    "date",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
)


def add_calendar_features(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with year, month, season and season year columns.

    December is assigned to the following season year. For example, December
    2020 and January 2021 both belong to winter 2021.
    """
    _require_columns(data, DAILY_COLUMNS)
    result = data.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    result["year"] = result["date"].dt.year
    result["month"] = result["date"].dt.month
    result["season"] = result["month"].map(SEASON_BY_MONTH)
    result["season_year"] = result["year"] + (result["month"] == 12).astype(int)
    return result


def calculate_annual_summary(
    data: pd.DataFrame,
    rolling_window: int = 10,
) -> pd.DataFrame:
    """Calculate annual temperature, hot-day and precipitation indicators.

    A hot day has a maximum temperature of at least 30 °C. A tropical night
    has a minimum temperature of at least 20 °C. A heavy-rain day has at least
    20 mm of precipitation.

    If one daily precipitation value is missing, precipitation indicators for
    that city-year remain missing instead of treating the missing value as zero.
    """
    _require_columns(data, (*DAILY_COLUMNS, "year"))
    if rolling_window < 2:
        raise ValueError("rolling_window must be at least 2 years.")

    work = data.copy()
    work["hot_day"] = work["temperature_2m_max"] >= 30
    work["tropical_night"] = work["temperature_2m_min"] >= 20
    work["heavy_rain_day"] = work["precipitation_sum"] >= 20

    keys = ["city", "city_slug", "year"]
    annual = (
        work.groupby(keys, observed=True)
        .agg(
            temperature_mean=("temperature_2m_mean", "mean"),
            hot_days=("hot_day", "sum"),
            tropical_nights=("tropical_night", "sum"),
            heavy_rain_days=("heavy_rain_day", "sum"),
            precipitation_missing_days=(
                "precipitation_sum",
                lambda values: values.isna().sum(),
            ),
            observed_days=("date", "size"),
        )
        .reset_index()
    )

    precipitation = (
        work.groupby(keys, observed=True)["precipitation_sum"]
        .sum(min_count=1)
        .reset_index(name="precipitation_total")
    )
    annual = annual.merge(precipitation, on=keys, validate="one_to_one")

    incomplete_rain = annual["precipitation_missing_days"] > 0
    annual.loc[
        incomplete_rain,
        ["precipitation_total", "heavy_rain_days"],
    ] = np.nan

    annual = annual.sort_values(["city_slug", "year"]).reset_index(drop=True)
    annual["temperature_rolling_mean"] = annual.groupby("city_slug")[
        "temperature_mean"
    ].transform(lambda values: values.rolling(rolling_window).mean())
    annual["hot_days_rolling_mean"] = annual.groupby("city_slug")[
        "hot_days"
    ].transform(lambda values: values.rolling(rolling_window).mean())
    annual["tropical_nights_rolling_mean"] = annual.groupby("city_slug")[
        "tropical_nights"
    ].transform(lambda values: values.rolling(rolling_window).mean())
    annual["precipitation_rolling_mean"] = annual.groupby("city_slug")[
        "precipitation_total"
    ].transform(lambda values: values.rolling(rolling_window).mean())
    return annual


def calculate_temperature_anomalies(
    annual_summary: pd.DataFrame,
    baseline_start: int = 1961,
    baseline_end: int = 1990,
) -> pd.DataFrame:
    """Add annual anomalies relative to each city's baseline temperature.

    An anomaly is the annual mean temperature minus the city's mean temperature
    during the baseline period. Positive values are warmer than the baseline.
    """
    _validate_baseline(baseline_start, baseline_end)
    _require_columns(
        annual_summary,
        ("city", "city_slug", "year", "temperature_mean"),
    )

    baseline = annual_summary.loc[
        annual_summary["year"].between(baseline_start, baseline_end)
    ]
    normals = (
        baseline.groupby(["city", "city_slug"], observed=True)["temperature_mean"]
        .mean()
        .reset_index(name="baseline_temperature")
    )
    result = annual_summary.merge(
        normals,
        on=["city", "city_slug"],
        how="left",
        validate="many_to_one",
    )
    if result["baseline_temperature"].isna().any():
        raise ValueError("The baseline period is missing for one or more cities.")

    result["temperature_anomaly"] = (
        result["temperature_mean"] - result["baseline_temperature"]
    )
    result["anomaly_rolling_mean"] = result.groupby("city_slug")[
        "temperature_anomaly"
    ].transform(lambda values: values.rolling(10).mean())
    return result


def calculate_temperature_trends(annual_summary: pd.DataFrame) -> pd.DataFrame:
    """Calculate one descriptive linear temperature trend for each city.

    The slope is calculated with ``numpy.polyfit`` and reported in degrees
    Celsius per decade. It describes the average direction of change but does
    not test statistical significance.
    """
    _require_columns(
        annual_summary,
        ("city", "city_slug", "year", "temperature_mean"),
    )

    rows = []
    for (city, city_slug), group in annual_summary.groupby(
        ["city", "city_slug"], observed=True
    ):
        valid = group[["year", "temperature_mean"]].dropna()
        if len(valid) < 2:
            raise ValueError(f"Not enough annual values for {city}.")
        slope, _ = np.polyfit(valid["year"], valid["temperature_mean"], 1)
        rows.append(
            {
                "city": city,
                "city_slug": city_slug,
                "start_year": int(valid["year"].min()),
                "end_year": int(valid["year"].max()),
                "slope_celsius_per_decade": float(slope * 10),
            }
        )

    return pd.DataFrame(rows).sort_values(
        "slope_celsius_per_decade", ascending=False
    ).reset_index(drop=True)


def calculate_seasonal_comparison(
    data: pd.DataFrame,
    early_period: tuple[int, int] = (1941, 1970),
    recent_period: tuple[int, int] = (1996, 2025),
) -> pd.DataFrame:
    """Compare seasonal mean temperatures in two historical periods.

    First, daily values are aggregated into individual seasons. Seasons that
    do not contain all three calendar months are excluded. The complete
    seasonal values are then averaged within the early and recent periods.
    """
    _validate_periods(early_period, recent_period)
    _require_columns(
        data,
        ("city", "city_slug", "date", "season", "season_year", "temperature_2m_mean"),
    )

    work = data.copy()
    work["year_month"] = work["date"].dt.to_period("M")
    seasonal = (
        work.groupby(
            ["city", "city_slug", "season_year", "season"],
            observed=True,
        )
        .agg(
            temperature_mean=("temperature_2m_mean", "mean"),
            months_present=("year_month", "nunique"),
        )
        .reset_index()
    )
    seasonal = seasonal.loc[seasonal["months_present"] == 3].copy()

    early = seasonal.loc[seasonal["season_year"].between(*early_period)].copy()
    early["period"] = f"{early_period[0]}–{early_period[1]}"
    recent = seasonal.loc[seasonal["season_year"].between(*recent_period)].copy()
    recent["period"] = f"{recent_period[0]}–{recent_period[1]}"

    combined = pd.concat([early, recent], ignore_index=True)
    return (
        combined.groupby(["city", "city_slug", "season", "period"], observed=True)
        .agg(
            temperature_mean=("temperature_mean", "mean"),
            seasons_observed=("season_year", "nunique"),
        )
        .reset_index()
    )


def compare_climate_periods(
    annual_summary: pd.DataFrame,
    metrics: Iterable[str],
    early_period: tuple[int, int] = (1941, 1970),
    recent_period: tuple[int, int] = (1996, 2025),
) -> pd.DataFrame:
    """Compare mean annual indicators between two non-overlapping periods."""
    metrics = list(metrics)
    if not metrics:
        raise ValueError("At least one metric is required.")
    _validate_periods(early_period, recent_period)
    _require_columns(annual_summary, ("city", "city_slug", "year", *metrics))

    rows = []
    for (city, city_slug), group in annual_summary.groupby(
        ["city", "city_slug"], observed=True
    ):
        early = group.loc[group["year"].between(*early_period)]
        recent = group.loc[group["year"].between(*recent_period)]
        if early.empty or recent.empty:
            raise ValueError(f"Comparison periods are incomplete for {city}.")

        for metric in metrics:
            early_mean = float(early[metric].mean())
            recent_mean = float(recent[metric].mean())
            rows.append(
                {
                    "city": city,
                    "city_slug": city_slug,
                    "metric": metric,
                    "early_period": f"{early_period[0]}–{early_period[1]}",
                    "recent_period": f"{recent_period[0]}–{recent_period[1]}",
                    "early_mean": early_mean,
                    "recent_mean": recent_mean,
                    "absolute_change": recent_mean - early_mean,
                }
            )
    return pd.DataFrame(rows)


def _require_columns(data: pd.DataFrame, columns: Iterable[str]) -> None:
    """Raise an error when a DataFrame does not contain required columns."""
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Data is missing required columns: {missing}.")


def _validate_baseline(start_year: int, end_year: int) -> None:
    """Check that the reference period is ordered and at least 20 years long."""
    if end_year < start_year:
        raise ValueError("baseline_end cannot precede baseline_start.")
    if end_year - start_year + 1 < 20:
        raise ValueError("The baseline must contain at least 20 years.")


def _validate_periods(
    early_period: tuple[int, int],
    recent_period: tuple[int, int],
) -> None:
    """Check that comparison periods are ordered and do not overlap."""
    if early_period[0] > early_period[1] or recent_period[0] > recent_period[1]:
        raise ValueError("A period cannot end before it starts.")
    if early_period[1] >= recent_period[0]:
        raise ValueError("Early and recent periods cannot overlap.")
