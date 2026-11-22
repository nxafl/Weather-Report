"""Clear, reusable charts for the climate analysis notebook."""

from collections.abc import Iterable
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


CITY_COLORS = {
    "milan": "#0072B2",
    "turin": "#56B4E9",
    "rome": "#009E73",
    "bari": "#E69F00",
    "palermo": "#D55E00",
    "cagliari": "#CC79A7",
}


def configure_plot_style() -> None:
    """Apply one consistent visual style to all project charts."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 180,
            "axes.titleweight": "bold",
            "legend.frameon": False,
        }
    )


def save_figure(figure: plt.Figure, output_directory: str | Path, filename: str) -> Path:
    """Save a figure in the requested folder and return its path."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / filename
    figure.savefig(output_path, bbox_inches="tight", facecolor="white")
    return output_path


def plot_annual_temperature(data: pd.DataFrame) -> plt.Figure:
    """Plot annual temperature and its trailing 10-year mean for each city."""
    _require_columns(
        data,
        ("city", "city_slug", "year", "temperature_mean", "temperature_rolling_mean"),
    )
    figure, axes = _city_facets(data, sharey=False)
    for axis, (city_slug, group) in zip(axes, _city_groups(data)):
        color = CITY_COLORS.get(city_slug, "#333333")
        axis.plot(
            group["year"], group["temperature_mean"],
            color=color, alpha=0.3, linewidth=1, label="Annual mean",
        )
        axis.plot(
            group["year"], group["temperature_rolling_mean"],
            color=color, linewidth=2.3, label="10-year mean",
        )
        axis.set(title=group["city"].iloc[0], xlabel="Year", ylabel="Temperature (°C)")
        axis.legend(fontsize=8)
    figure.suptitle("Annual mean temperature, 1940–2025")
    figure.tight_layout()
    return figure


def plot_temperature_anomalies(data: pd.DataFrame) -> plt.Figure:
    """Plot annual temperature anomalies relative to the 1961–1990 baseline."""
    _require_columns(
        data,
        ("city", "city_slug", "year", "temperature_anomaly", "anomaly_rolling_mean"),
    )
    figure, axes = _city_facets(data, sharey=True)
    for axis, (_, group) in zip(axes, _city_groups(data)):
        colors = ["#D55E00" if value >= 0 else "#0072B2" for value in group["temperature_anomaly"]]
        axis.bar(group["year"], group["temperature_anomaly"], color=colors, width=0.9)
        axis.plot(group["year"], group["anomaly_rolling_mean"], color="#222222", linewidth=2)
        axis.axhline(0, color="#222222", linewidth=0.8)
        axis.set(title=group["city"].iloc[0], xlabel="Year", ylabel="Anomaly (°C)")
    figure.suptitle("Annual temperature anomalies relative to 1961–1990")
    figure.tight_layout()
    return figure


def plot_temperature_trends(trends: pd.DataFrame) -> plt.Figure:
    """Compare descriptive temperature slopes across cities."""
    _require_columns(trends, ("city", "slope_celsius_per_decade"))
    ordered = trends.sort_values("slope_celsius_per_decade")
    figure, axis = plt.subplots(figsize=(9, 5.5))
    sns.barplot(
        data=ordered,
        x="slope_celsius_per_decade",
        y="city",
        hue="city",
        palette="rocket",
        legend=False,
        ax=axis,
    )
    axis.axvline(0, color="#222222", linewidth=0.8)
    axis.set(
        title="Descriptive temperature trend, 1940–2025",
        xlabel="Temperature change (°C per decade)",
        ylabel="",
    )
    figure.tight_layout()
    return figure


def plot_hot_days(data: pd.DataFrame) -> plt.Figure:
    """Plot 10-year averages of hot days and tropical nights for each city."""
    _require_columns(
        data,
        (
            "city", "city_slug", "year",
            "hot_days_rolling_mean", "tropical_nights_rolling_mean",
        ),
    )
    figure, axes = _city_facets(data, sharey=False)
    for axis, (_, group) in zip(axes, _city_groups(data)):
        axis.plot(
            group["year"], group["hot_days_rolling_mean"],
            color="#E69F00", linewidth=2, label="Days ≥ 30 °C",
        )
        axis.plot(
            group["year"], group["tropical_nights_rolling_mean"],
            color="#CC79A7", linewidth=2, label="Nights ≥ 20 °C",
        )
        axis.set(title=group["city"].iloc[0], xlabel="Year", ylabel="Days per year")
        axis.legend(fontsize=8)
    figure.suptitle("Hot days and tropical nights: trailing 10-year averages")
    figure.tight_layout()
    return figure


def plot_precipitation(data: pd.DataFrame) -> plt.Figure:
    """Plot annual precipitation and its trailing 10-year mean for each city."""
    _require_columns(
        data,
        ("city", "city_slug", "year", "precipitation_total", "precipitation_rolling_mean"),
    )
    figure, axes = _city_facets(data, sharey=False)
    for axis, (city_slug, group) in zip(axes, _city_groups(data)):
        color = CITY_COLORS.get(city_slug, "#333333")
        axis.plot(group["year"], group["precipitation_total"], color=color, alpha=0.25)
        axis.plot(group["year"], group["precipitation_rolling_mean"], color=color, linewidth=2.3)
        axis.set(title=group["city"].iloc[0], xlabel="Year", ylabel="Precipitation (mm)")
    figure.suptitle("Annual precipitation and trailing 10-year mean")
    figure.tight_layout()
    return figure


def plot_seasonal_comparison(data: pd.DataFrame) -> plt.Figure:
    """Compare mean seasonal temperature in the early and recent periods."""
    _require_columns(
        data,
        ("city", "city_slug", "season", "period", "temperature_mean"),
    )
    season_order = ["Winter", "Spring", "Summer", "Autumn"]
    period_order = list(data["period"].drop_duplicates())
    figure, axes = _city_facets(data, sharey=False)
    for axis, (_, group) in zip(axes, _city_groups(data, sort_column="season")):
        sns.barplot(
            data=group,
            x="season",
            y="temperature_mean",
            hue="period",
            order=season_order,
            hue_order=period_order,
            palette=["#56B4E9", "#D55E00"],
            ax=axis,
        )
        axis.set(title=group["city"].iloc[0], xlabel="", ylabel="Temperature (°C)")
        axis.tick_params(axis="x", rotation=20)
        axis.legend(title="Period", fontsize=8)
    figure.suptitle("Seasonal temperature: historical and recent periods")
    figure.tight_layout()
    return figure


def _city_groups(
    data: pd.DataFrame,
    sort_column: str = "year",
) -> list[tuple[str, pd.DataFrame]]:
    """Return city groups in the stable project order."""
    present = list(data["city_slug"].drop_duplicates())
    order = [city for city in CITY_COLORS if city in present]
    groups = []
    for city_slug in order:
        group = data.loc[data["city_slug"] == city_slug]
        if sort_column in group.columns:
            group = group.sort_values(sort_column)
        groups.append((city_slug, group))
    return groups


def _city_facets(
    data: pd.DataFrame,
    sharey: bool,
) -> tuple[plt.Figure, list[plt.Axes]]:
    """Create a two-column subplot grid for the cities in a table."""
    city_count = data["city_slug"].nunique()
    if city_count == 0:
        raise ValueError("Cannot plot an empty DataFrame.")
    rows = (city_count + 1) // 2
    figure, axes = plt.subplots(rows, 2, figsize=(15, 4 * rows), sharey=sharey, squeeze=False)
    visible_axes = list(axes.ravel()[:city_count])
    for axis in axes.ravel()[city_count:]:
        axis.set_visible(False)
    return figure, visible_axes


def _require_columns(data: pd.DataFrame, columns: Iterable[str]) -> None:
    """Raise an error when plotting data does not contain required columns."""
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Plotting data is missing required columns: {missing}.")
