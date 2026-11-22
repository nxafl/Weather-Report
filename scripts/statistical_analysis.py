"""Inferential trend models used after exploratory climate analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass(frozen=True, slots=True)
class CityInteractionResult:
    """Results from the city-by-year interaction regression.

    Attributes
    ----------
    model:
        Fitted Statsmodels regression result with HC3 robust covariance.
    city_slopes:
        Estimated temperature slope and 95% confidence interval for every city.
    interaction_effects:
        Difference between each city's slope and the reference-city slope.
    diagnostics:
        Compact model-level statistics for reporting.
    """

    model: Any
    city_slopes: Any
    interaction_effects: Any
    diagnostics: dict[str, float | int | str]


def calculate_seasonal_indicators(data: Any) -> Any:
    """Aggregate daily observations into complete meteorological seasons.

    Winter is identified by ``season_year`` so December belongs with the next
    January and February. Boundary winters containing fewer than three months
    are excluded. Temperature variables are averaged, while precipitation is
    summed only when all daily values are available.

    Parameters
    ----------
    data:
        Daily DataFrame enriched by ``add_calendar_features``.

    Returns
    -------
    pandas.DataFrame
        One row per city, complete season and season year.
    """
    pd = _require_pandas()
    required = (
        "city",
        "city_slug",
        "date",
        "month",
        "season",
        "season_year",
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    )
    _require_columns(data, required)

    work = data.copy()
    work["daily_temperature_range"] = (
        work["temperature_2m_max"] - work["temperature_2m_min"]
    )
    keys = ["city", "city_slug", "season_year", "season"]
    grouped = work.groupby(keys, observed=True, sort=True)
    seasonal = grouped.agg(
        temperature_mean=("temperature_2m_mean", "mean"),
        temperature_max_mean=("temperature_2m_max", "mean"),
        temperature_min_mean=("temperature_2m_min", "mean"),
        diurnal_temperature_range=("daily_temperature_range", "mean"),
        precipitation_missing_days=("precipitation_sum", lambda values: values.isna().sum()),
        observed_days=("date", "size"),
        observed_months=("month", "nunique"),
    ).reset_index()
    precipitation = grouped["precipitation_sum"].sum(min_count=1).reset_index(
        name="precipitation_total"
    )
    seasonal = seasonal.merge(
        precipitation,
        on=keys,
        how="left",
        validate="one_to_one",
    )
    seasonal = seasonal.loc[seasonal["observed_months"] == 3].copy()
    seasonal.loc[
        seasonal["precipitation_missing_days"] > 0,
        "precipitation_total",
    ] = pd.NA
    seasonal = seasonal.rename(columns={"season_year": "year"})
    return seasonal.sort_values(["city_slug", "year", "season"]).reset_index(drop=True)


def fit_grouped_linear_trends(
    data: Any,
    value_column: str,
    *,
    group_columns: Sequence[str] = ("city", "city_slug"),
    time_column: str = "year",
    confidence_level: float = 0.95,
    hac_lags: int = 1,
) -> Any:
    """Fit one time trend per group with HAC confidence intervals.

    Ordinary least squares estimates the trend, while Newey–West HAC standard
    errors reduce sensitivity to short-range autocorrelation and changing
    residual variance. Slopes and confidence intervals are expressed per
    decade when the time variable is measured in years.

    Parameters
    ----------
    data:
        DataFrame containing groups, time and the response variable.
    value_column:
        Numeric response to model.
    group_columns:
        Columns defining independent trend models.
    time_column:
        Numeric time variable, normally ``year``.
    confidence_level:
        Confidence level strictly between zero and one.
    hac_lags:
        Maximum lag used by the HAC covariance estimator.

    Returns
    -------
    pandas.DataFrame
        Trend, confidence interval, p-value, R² and observation count per group.
    """
    pd = _require_pandas()
    sm = _require_statsmodels()
    _validate_confidence_level(confidence_level)
    if hac_lags < 0:
        raise ValueError("hac_lags cannot be negative.")

    groups = list(group_columns)
    if not groups:
        raise ValueError("At least one group column is required.")
    _require_columns(data, (*groups, time_column, value_column))
    alpha = 1.0 - confidence_level
    rows: list[dict[str, Any]] = []

    for group_key, group in data.groupby(groups, observed=True, sort=True):
        valid = (
            group[[*groups, time_column, value_column]]
            .dropna(subset=[time_column, value_column])
            .sort_values(time_column)
        )
        if len(valid) < 10:
            raise ValueError(
                f"At least 10 observations are required for group {group_key!r}."
            )

        start_time = float(valid[time_column].min())
        centered_time = valid[time_column].astype(float) - start_time
        design = sm.add_constant(centered_time.rename("time"))
        model = sm.OLS(valid[value_column].astype(float), design).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": hac_lags},
        )
        confidence_interval = model.conf_int(alpha=alpha).loc["time"]

        key_values = group_key if isinstance(group_key, tuple) else (group_key,)
        row = dict(zip(groups, key_values))
        row.update(
            {
                "metric": value_column,
                "start_year": int(valid[time_column].min()),
                "end_year": int(valid[time_column].max()),
                "observations": len(valid),
                "slope_per_decade": float(model.params["time"] * 10),
                "ci_lower_per_decade": float(confidence_interval.iloc[0] * 10),
                "ci_upper_per_decade": float(confidence_interval.iloc[1] * 10),
                "p_value": float(model.pvalues["time"]),
                "r_squared": float(model.rsquared),
                "hac_lags": hac_lags,
            }
        )
        rows.append(row)

    return pd.DataFrame(rows)


def fit_city_year_interaction(
    annual_data: Any,
    *,
    value_column: str = "temperature_mean",
    reference_city_slug: str = "milan",
    confidence_level: float = 0.95,
) -> CityInteractionResult:
    """Fit a pooled city-by-year interaction model with HC3 covariance.

    The model includes a common time slope, city intercept differences and one
    time interaction for every non-reference city. Interaction terms test
    whether each city's trend differs from the reference city's trend.
    """
    pd = _require_pandas()
    sm = _require_statsmodels()
    np = _require_numpy()
    _validate_confidence_level(confidence_level)
    _require_columns(annual_data, ("city", "city_slug", "year", value_column))

    work = annual_data[["city", "city_slug", "year", value_column]].dropna().copy()
    if reference_city_slug not in set(work["city_slug"]):
        raise ValueError(f"Reference city '{reference_city_slug}' is not present.")

    start_year = int(work["year"].min())
    work["year_centered"] = work["year"].astype(float) - start_year
    city_order = [reference_city_slug] + sorted(
        city for city in work["city_slug"].unique() if city != reference_city_slug
    )
    design = pd.DataFrame(index=work.index)
    design["year_centered"] = work["year_centered"]
    for city_slug in city_order[1:]:
        indicator = (work["city_slug"] == city_slug).astype(float)
        design[f"city_{city_slug}"] = indicator
        design[f"year_x_{city_slug}"] = work["year_centered"] * indicator
    design = sm.add_constant(design)

    model = sm.OLS(work[value_column].astype(float), design).fit(cov_type="HC3")
    alpha = 1.0 - confidence_level
    city_names = (
        work[["city_slug", "city"]].drop_duplicates().set_index("city_slug")["city"]
    )
    slope_rows: list[dict[str, Any]] = []
    interaction_rows: list[dict[str, Any]] = []

    for city_slug in city_order:
        contrast = np.zeros(len(model.params))
        contrast[model.params.index.get_loc("year_centered")] = 1.0
        interaction_name = f"year_x_{city_slug}"
        if city_slug != reference_city_slug:
            contrast[model.params.index.get_loc(interaction_name)] = 1.0
        test = model.t_test(contrast)
        interval = test.conf_int(alpha=alpha)[0]
        slope_rows.append(
            {
                "city": str(city_names.loc[city_slug]),
                "city_slug": city_slug,
                "reference_city_slug": reference_city_slug,
                "slope_per_decade": float(test.effect.item() * 10),
                "ci_lower_per_decade": float(interval[0] * 10),
                "ci_upper_per_decade": float(interval[1] * 10),
                "p_value": float(test.pvalue.item()),
            }
        )

        if city_slug != reference_city_slug:
            coefficient = model.params[interaction_name]
            interval = model.conf_int(alpha=alpha).loc[interaction_name]
            interaction_rows.append(
                {
                    "city": str(city_names.loc[city_slug]),
                    "city_slug": city_slug,
                    "reference_city_slug": reference_city_slug,
                    "slope_difference_per_decade": float(coefficient * 10),
                    "ci_lower_per_decade": float(interval.iloc[0] * 10),
                    "ci_upper_per_decade": float(interval.iloc[1] * 10),
                    "p_value": float(model.pvalues[interaction_name]),
                }
            )

    diagnostics: dict[str, float | int | str] = {
        "response": value_column,
        "reference_city_slug": reference_city_slug,
        "observations": int(model.nobs),
        "r_squared": float(model.rsquared),
        "adjusted_r_squared": float(model.rsquared_adj),
        "covariance_type": "HC3",
    }
    return CityInteractionResult(
        model=model,
        city_slopes=pd.DataFrame(slope_rows),
        interaction_effects=pd.DataFrame(interaction_rows),
        diagnostics=diagnostics,
    )


def add_significance_labels(
    trends: Any,
    *,
    p_value_column: str = "p_value",
) -> Any:
    """Add conventional significance symbols for compact result tables.

    Symbols are descriptive reporting aids: ``***`` for p < 0.001, ``**`` for
    p < 0.01, ``*`` for p < 0.05 and an empty string otherwise.
    """
    pd = _require_pandas()
    _require_columns(trends, (p_value_column,))
    result = trends.copy()
    result["significance"] = pd.cut(
        result[p_value_column],
        bins=[-float("inf"), 0.001, 0.01, 0.05, float("inf")],
        labels=["***", "**", "*", ""],
        right=False,
    ).astype("string")
    return result


def _validate_confidence_level(confidence_level: float) -> None:
    """Validate a confidence level used by model intervals."""
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be strictly between 0 and 1.")


def _require_columns(data: Any, columns: Iterable[str]) -> None:
    """Raise a clear error when model input lacks required columns."""
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Model data is missing required columns: {missing}.")


def _require_pandas() -> Any:
    """Import pandas with a project-specific installation hint."""
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "pandas is required for statistical analysis. Install requirements.txt."
        ) from exc
    return pd


def _require_numpy() -> Any:
    """Import NumPy with a project-specific installation hint."""
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "numpy is required for statistical analysis. Install requirements.txt."
        ) from exc
    return np


def _require_statsmodels() -> Any:
    """Import Statsmodels with a project-specific installation hint."""
    try:
        import statsmodels.api as sm
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "statsmodels is required for regression analysis. Install requirements.txt."
        ) from exc
    return sm
