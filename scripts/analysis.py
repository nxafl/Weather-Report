"""Feature engineering and descriptive climate indicators for the EDA notebook."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


MONTH_NAMES: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""Calendar month names in display order."""

SEASON_BY_MONTH: dict[int, str] = {
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
"""Meteorological season assigned to each calendar month."""

CORE_DAILY_COLUMNS: tuple[str, ...] = (
    "city",
    "city_slug",
    "date",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
)
"""Columns required to calculate the project's exploratory indicators."""


def add_calendar_features(data: Any) -> Any:
    """Add calendar fields required for temporal aggregation.

    Parameters
    ----------
    data:
        Daily pandas DataFrame with a parsed ``date`` column.

    Returns
    -------
    pandas.DataFrame
        Independent copy with year, month, ordered month name, meteorological
        season, season year, decade and day-of-year fields.

    Notes
    -----
    December is assigned to the following ``season_year`` so that December
    2020, January 2021 and February 2021 form one winter season.
    """
    pd = _require_pandas()
    _require_columns(data, CORE_DAILY_COLUMNS)

    result = data.copy()
    if not pd.api.types.is_datetime64_any_dtype(result["date"]):
        result["date"] = pd.to_datetime(result["date"], errors="raise")

    result["year"] = result["date"].dt.year.astype("int16")
    result["month"] = result["date"].dt.month.astype("int8")
    result["month_name"] = pd.Categorical(
        result["date"].dt.month_name(),
        categories=MONTH_NAMES,
        ordered=True,
    )
    result["season"] = pd.Categorical(
        result["month"].map(SEASON_BY_MONTH),
        categories=["Winter", "Spring", "Summer", "Autumn"],
        ordered=True,
    )
    result["season_year"] = (
        result["year"] + (result["month"] == 12).astype("int16")
    ).astype("int16")
    result["decade"] = ((result["year"] // 10) * 10).astype("int16")
    result["day_of_year"] = result["date"].dt.day_of_year.astype("int16")
    return result


def calculate_monthly_summary(data: Any) -> Any:
    """Aggregate daily observations to one row per city, year and month.

    Temperature fields are averaged. Precipitation is summed only when every
    daily value in the month is present; otherwise the monthly total remains
    missing rather than silently treating a missing day as zero.
    """
    pd = _require_pandas()
    required = (*CORE_DAILY_COLUMNS, "year", "month", "month_name")
    _require_columns(data, required)

    keys = ["city", "city_slug", "year", "month", "month_name"]
    grouped = data.groupby(keys, observed=True, sort=True)
    monthly = grouped.agg(
        temperature_mean=("temperature_2m_mean", "mean"),
        temperature_max_mean=("temperature_2m_max", "mean"),
        temperature_min_mean=("temperature_2m_min", "mean"),
        precipitation_missing_days=("precipitation_sum", lambda values: values.isna().sum()),
        observed_days=("date", "size"),
    ).reset_index()

    precipitation = grouped["precipitation_sum"].sum(min_count=1).reset_index(
        name="precipitation_total"
    )
    monthly = monthly.merge(precipitation, on=keys, how="left", validate="one_to_one")
    incomplete = monthly["precipitation_missing_days"] > 0
    monthly.loc[incomplete, "precipitation_total"] = pd.NA
    return monthly.sort_values(["city_slug", "year", "month"]).reset_index(drop=True)


def calculate_monthly_climatology(
    monthly_summary: Any,
    baseline_start: int = 1961,
    baseline_end: int = 1990,
) -> Any:
    """Calculate mean monthly climate conditions for a fixed baseline.

    Parameters
    ----------
    monthly_summary:
        Output of :func:`calculate_monthly_summary`.
    baseline_start, baseline_end:
        Inclusive baseline years. The project uses 1961–1990.

    Returns
    -------
    pandas.DataFrame
        One row per city and calendar month with baseline temperature and
        precipitation normals.
    """
    _validate_baseline(baseline_start, baseline_end)
    _require_columns(
        monthly_summary,
        ("city", "city_slug", "year", "month", "month_name", "temperature_mean", "precipitation_total"),
    )
    baseline = monthly_summary.loc[
        monthly_summary["year"].between(baseline_start, baseline_end)
    ]
    if baseline.empty:
        raise ValueError("The requested baseline does not overlap the monthly data.")

    return (
        baseline.groupby(
            ["city", "city_slug", "month", "month_name"],
            observed=True,
            sort=True,
        )
        .agg(
            baseline_temperature=("temperature_mean", "mean"),
            baseline_precipitation=("precipitation_total", "mean"),
            baseline_years=("year", "nunique"),
        )
        .reset_index()
        .sort_values(["city_slug", "month"])
        .reset_index(drop=True)
    )


def calculate_monthly_temperature_anomalies(
    monthly_summary: Any,
    climatology: Any,
) -> Any:
    """Subtract each city's baseline calendar-month temperature normal.

    Returns a copy of the monthly summary with ``temperature_anomaly``. A July
    observation is therefore compared only with baseline Julys for that city.
    """
    _require_columns(monthly_summary, ("city_slug", "month", "temperature_mean"))
    _require_columns(climatology, ("city_slug", "month", "baseline_temperature"))
    reference = climatology[["city_slug", "month", "baseline_temperature"]]
    result = monthly_summary.merge(
        reference,
        on=["city_slug", "month"],
        how="left",
        validate="many_to_one",
    )
    if result["baseline_temperature"].isna().any():
        raise ValueError("Monthly climatology is incomplete for one or more cities.")
    result["temperature_anomaly"] = (
        result["temperature_mean"] - result["baseline_temperature"]
    )
    return result


def calculate_annual_indicators(data: Any, rolling_window: int = 10) -> Any:
    """Calculate yearly temperature, heat and precipitation indicators.

    Indicators include annual mean temperature, observed temperature range,
    hot days, very hot days, tropical nights, total precipitation, wet days,
    heavy-rain days, maximum one-day precipitation and wet-day intensity.

    A precipitation year containing any missing daily value is deliberately
    assigned missing precipitation indicators. This prevents the incomplete
    precipitation record for 1940 from being reported as a true annual total.
    """
    pd = _require_pandas()
    _require_columns(data, (*CORE_DAILY_COLUMNS, "year"))
    if rolling_window < 2:
        raise ValueError("rolling_window must be at least 2 years.")

    work = data.copy()
    work["daily_temperature_range"] = (
        work["temperature_2m_max"] - work["temperature_2m_min"]
    )
    work["is_hot_day"] = work["temperature_2m_max"] >= 30.0
    work["is_very_hot_day"] = work["temperature_2m_max"] >= 35.0
    work["is_tropical_night"] = work["temperature_2m_min"] >= 20.0
    work["is_wet_day"] = work["precipitation_sum"] >= 1.0
    work["is_heavy_rain_day"] = work["precipitation_sum"] >= 20.0

    keys = ["city", "city_slug", "year"]
    annual = (
        work.groupby(keys, observed=True, sort=True)
        .agg(
            temperature_mean=("temperature_2m_mean", "mean"),
            temperature_max_mean=("temperature_2m_max", "mean"),
            temperature_min_mean=("temperature_2m_min", "mean"),
            diurnal_temperature_range=("daily_temperature_range", "mean"),
            temperature_max=("temperature_2m_max", "max"),
            temperature_min=("temperature_2m_min", "min"),
            hot_days=("is_hot_day", "sum"),
            very_hot_days=("is_very_hot_day", "sum"),
            tropical_nights=("is_tropical_night", "sum"),
            wet_days=("is_wet_day", "sum"),
            heavy_rain_days=("is_heavy_rain_day", "sum"),
            rx1day=("precipitation_sum", "max"),
            precipitation_missing_days=("precipitation_sum", lambda values: values.isna().sum()),
            observed_days=("date", "size"),
        )
        .reset_index()
    )

    precipitation = (
        work.groupby(keys, observed=True, sort=True)["precipitation_sum"]
        .sum(min_count=1)
        .reset_index(name="precipitation_total")
    )
    annual = annual.merge(precipitation, on=keys, how="left", validate="one_to_one")
    incomplete = annual["precipitation_missing_days"] > 0
    precipitation_columns = [
        "precipitation_total",
        "wet_days",
        "heavy_rain_days",
        "rx1day",
    ]
    annual.loc[incomplete, precipitation_columns] = pd.NA
    annual["wet_day_intensity"] = annual["precipitation_total"].div(
        annual["wet_days"].replace(0, pd.NA)
    )

    annual = annual.sort_values(["city_slug", "year"]).reset_index(drop=True)
    annual["temperature_rolling_mean"] = annual.groupby(
        "city_slug", observed=True
    )["temperature_mean"].transform(
        lambda values: values.rolling(rolling_window, min_periods=rolling_window).mean()
    )
    annual["precipitation_rolling_mean"] = annual.groupby(
        "city_slug", observed=True
    )["precipitation_total"].transform(
        lambda values: values.rolling(rolling_window, min_periods=rolling_window).mean()
    )
    return annual


def add_annual_temperature_anomalies(
    annual_indicators: Any,
    baseline_start: int = 1961,
    baseline_end: int = 1990,
) -> Any:
    """Add fixed-baseline annual temperature anomalies for every city."""
    _validate_baseline(baseline_start, baseline_end)
    _require_columns(
        annual_indicators,
        ("city", "city_slug", "year", "temperature_mean"),
    )
    baseline = annual_indicators.loc[
        annual_indicators["year"].between(baseline_start, baseline_end)
    ]
    normals = (
        baseline.groupby(["city", "city_slug"], observed=True)["temperature_mean"]
        .mean()
        .rename("baseline_temperature")
        .reset_index()
    )
    result = annual_indicators.merge(
        normals,
        on=["city", "city_slug"],
        how="left",
        validate="many_to_one",
    )
    if result["baseline_temperature"].isna().any():
        raise ValueError("Annual baseline is incomplete for one or more cities.")
    result["temperature_anomaly"] = (
        result["temperature_mean"] - result["baseline_temperature"]
    )
    result["anomaly_rolling_mean"] = result.groupby(
        "city_slug", observed=True
    )["temperature_anomaly"].transform(
        lambda values: values.rolling(10, min_periods=10).mean()
    )
    return result


def calculate_heatwave_indicators(
    data: Any,
    baseline_start: int = 1961,
    baseline_end: int = 1990,
    percentile: float = 0.90,
    minimum_duration: int = 3,
    summer_months: Iterable[int] = (6, 7, 8),
) -> tuple[Any, Any]:
    """Identify summer heatwaves using city-specific historical thresholds.

    A heatwave is a sequence of at least ``minimum_duration`` consecutive
    summer days whose maximum temperature is at or above the city's specified
    baseline percentile.

    Returns
    -------
    tuple of pandas.DataFrame
        The first table contains one threshold per city. The second contains
        annual heatwave count, total heatwave days and maximum duration.
    """
    pd = _require_pandas()
    _validate_baseline(baseline_start, baseline_end)
    _require_columns(data, (*CORE_DAILY_COLUMNS, "year", "month"))
    if not 0 < percentile < 1:
        raise ValueError("percentile must be strictly between 0 and 1.")
    if minimum_duration < 2:
        raise ValueError("minimum_duration must be at least 2 days.")

    summer_months = tuple(summer_months)
    if not summer_months or any(month not in range(1, 13) for month in summer_months):
        raise ValueError("summer_months must contain valid calendar months.")

    baseline = data.loc[
        data["year"].between(baseline_start, baseline_end)
        & data["month"].isin(summer_months)
    ]
    thresholds = (
        baseline.groupby(["city", "city_slug"], observed=True)["temperature_2m_max"]
        .quantile(percentile)
        .rename("heat_threshold")
        .reset_index()
    )
    if thresholds.empty or thresholds["heat_threshold"].isna().any():
        raise ValueError("Cannot calculate heat thresholds from the selected baseline.")

    summer = data.loc[data["month"].isin(summer_months)].merge(
        thresholds,
        on=["city", "city_slug"],
        how="left",
        validate="many_to_one",
    )
    summer = summer.sort_values(["city_slug", "date"]).copy()
    summer["above_heat_threshold"] = (
        summer["temperature_2m_max"] >= summer["heat_threshold"]
    )

    rows: list[dict[str, Any]] = []
    for (city, city_slug, year), group in summer.groupby(
        ["city", "city_slug", "year"], observed=True, sort=True
    ):
        hot = group["above_heat_threshold"].astype(bool)
        sequence_id = (~hot).cumsum()
        run_lengths = hot.groupby(sequence_id).sum()
        qualifying = run_lengths.loc[run_lengths >= minimum_duration]
        rows.append(
            {
                "city": city,
                "city_slug": city_slug,
                "year": int(year),
                "heatwave_count": int(len(qualifying)),
                "heatwave_days": int(qualifying.sum()),
                "maximum_heatwave_duration": int(qualifying.max()) if len(qualifying) else 0,
            }
        )

    indicators = pd.DataFrame(rows).sort_values(["city_slug", "year"]).reset_index(drop=True)
    return thresholds, indicators


def estimate_temperature_trends(annual_indicators: Any) -> Any:
    """Estimate descriptive linear temperature trends for each city.

    The returned slope is expressed in degrees Celsius per decade. These are
    exploratory ordinary-least-squares summaries; formal inference and robust
    trend sensitivity checks belong in the statistical-analysis stage.
    """
    np = _require_numpy()
    pd = _require_pandas()
    _require_columns(
        annual_indicators,
        ("city", "city_slug", "year", "temperature_mean"),
    )

    rows: list[dict[str, Any]] = []
    for (city, city_slug), group in annual_indicators.groupby(
        ["city", "city_slug"], observed=True, sort=True
    ):
        valid = group[["year", "temperature_mean"]].dropna()
        if len(valid) < 2:
            raise ValueError(f"Not enough annual observations for city '{city_slug}'.")
        slope, intercept = np.polyfit(valid["year"], valid["temperature_mean"], 1)
        fitted = slope * valid["year"].to_numpy() + intercept
        residual = valid["temperature_mean"].to_numpy() - fitted
        total = valid["temperature_mean"].to_numpy() - valid["temperature_mean"].mean()
        total_variation = float((total**2).sum())
        r_squared = (
            1.0 - float((residual**2).sum() / total_variation)
            if total_variation > 0
            else float("nan")
        )
        rows.append(
            {
                "city": city,
                "city_slug": city_slug,
                "start_year": int(valid["year"].min()),
                "end_year": int(valid["year"].max()),
                "observations": len(valid),
                "slope_celsius_per_decade": float(slope * 10),
                "r_squared": r_squared,
            }
        )
    return pd.DataFrame(rows).sort_values("slope_celsius_per_decade", ascending=False).reset_index(drop=True)


def merge_annual_indicators(annual_indicators: Any, heatwave_indicators: Any) -> Any:
    """Merge annual climate and heatwave tables with one-to-one validation."""
    _require_columns(annual_indicators, ("city", "city_slug", "year"))
    _require_columns(heatwave_indicators, ("city", "city_slug", "year"))
    return annual_indicators.merge(
        heatwave_indicators,
        on=["city", "city_slug", "year"],
        how="left",
        validate="one_to_one",
    )


def compare_climate_periods(
    annual_indicators: Any,
    metrics: Iterable[str],
    early_period: tuple[int, int] = (1941, 1970),
    recent_period: tuple[int, int] = (1996, 2025),
) -> Any:
    """Compare mean annual indicators between two non-overlapping periods.

    Parameters
    ----------
    annual_indicators:
        Annual city-level indicator table.
    metrics:
        Numeric columns to compare.
    early_period, recent_period:
        Inclusive year intervals. Defaults provide two complete 30-year
        periods while avoiding incomplete 1940 precipitation.

    Returns
    -------
    pandas.DataFrame
        Long-form table with early and recent means, absolute change and
        percentage change for each city-metric pair.
    """
    pd = _require_pandas()
    metric_names = list(metrics)
    if not metric_names:
        raise ValueError("At least one metric is required for period comparison.")
    _require_columns(
        annual_indicators,
        ("city", "city_slug", "year", *metric_names),
    )
    _validate_period_pair(early_period, recent_period)

    rows: list[dict[str, Any]] = []
    for (city, city_slug), group in annual_indicators.groupby(
        ["city", "city_slug"], observed=True, sort=True
    ):
        early = group.loc[group["year"].between(*early_period)]
        recent = group.loc[group["year"].between(*recent_period)]
        if early.empty or recent.empty:
            raise ValueError(f"Comparison periods are incomplete for city '{city_slug}'.")
        for metric in metric_names:
            early_mean = float(early[metric].mean())
            recent_mean = float(recent[metric].mean())
            absolute_change = recent_mean - early_mean
            percentage_change = (
                absolute_change / early_mean * 100 if early_mean != 0 else float("nan")
            )
            rows.append(
                {
                    "city": city,
                    "city_slug": city_slug,
                    "metric": metric,
                    "early_period": f"{early_period[0]}–{early_period[1]}",
                    "recent_period": f"{recent_period[0]}–{recent_period[1]}",
                    "early_mean": early_mean,
                    "recent_mean": recent_mean,
                    "absolute_change": absolute_change,
                    "percentage_change": percentage_change,
                }
            )
    return pd.DataFrame(rows)


def _validate_baseline(start_year: int, end_year: int) -> None:
    """Validate an inclusive climatological baseline interval."""
    if end_year < start_year:
        raise ValueError("baseline_end cannot precede baseline_start.")
    if end_year - start_year + 1 < 20:
        raise ValueError("A climatological baseline should span at least 20 years.")


def _validate_period_pair(
    early_period: tuple[int, int],
    recent_period: tuple[int, int],
) -> None:
    """Validate ordered, non-overlapping comparison periods."""
    if early_period[1] < early_period[0] or recent_period[1] < recent_period[0]:
        raise ValueError("Period end years cannot precede their start years.")
    if early_period[1] >= recent_period[0]:
        raise ValueError("Early and recent periods must not overlap.")


def _require_columns(data: Any, columns: Iterable[str]) -> None:
    """Raise a clear error when a DataFrame lacks required columns."""
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Data is missing required columns: {missing}.")


def _require_pandas() -> Any:
    """Import pandas with a project-specific installation hint."""
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "pandas is required for climate analysis. Install requirements.txt."
        ) from exc
    return pd


def _require_numpy() -> Any:
    """Import NumPy with a project-specific installation hint."""
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "numpy is required for climate analysis. Install requirements.txt."
        ) from exc
    return np
