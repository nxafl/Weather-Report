"""Reusable static visualizations for exploratory climate analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


CITY_COLORS: dict[str, str] = {
    "milan": "#0072B2",
    "turin": "#56B4E9",
    "rome": "#009E73",
    "bari": "#E69F00",
    "palermo": "#D55E00",
    "cagliari": "#CC79A7",
}
"""Color-blind-friendly city colors used consistently across charts."""


def configure_plot_style() -> None:
    """Apply a consistent, accessible plotting style for all project figures."""
    plt, sns = _plot_libraries()
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 180,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "figure.titlesize": 15,
            "legend.frameon": False,
        }
    )


def save_figure(
    figure: Any,
    output_directory: str | Path,
    filename: str,
    *,
    overwrite: bool = True,
) -> Path:
    """Save a Matplotlib figure atomically and return its resolved path.

    Parameters
    ----------
    figure:
        Matplotlib figure returned by one of this module's plotting functions.
    output_directory:
        Destination directory, created when missing.
    filename:
        File name including a supported extension such as ``.png``.
    overwrite:
        When false, refuse to replace an existing figure.
    """
    directory = Path(output_directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if not destination.suffix:
        raise ValueError("filename must include an image extension.")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Figure already exists: {destination}")

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        figure.savefig(
            temporary,
            format=destination.suffix.lstrip("."),
            bbox_inches="tight",
            facecolor="white",
        )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def plot_temperature_distributions(data: Any) -> Any:
    """Compare daily mean-temperature distributions across cities."""
    plt, sns = _plot_libraries()
    _require_columns(data, ("city", "city_slug", "temperature_2m_mean"))
    order = _city_names_in_order(data)
    palette = _palette_for_city_names(data)

    figure, axis = plt.subplots(figsize=(11, 5.5))
    sns.boxplot(
        data=data,
        x="city",
        y="temperature_2m_mean",
        order=order,
        hue="city",
        palette=palette,
        legend=False,
        showfliers=False,
        ax=axis,
    )
    axis.set(
        title="Distribution of daily mean temperature, 1940–2025",
        xlabel="",
        ylabel="Daily mean temperature (°C)",
    )
    figure.tight_layout()
    return figure


def plot_monthly_climatology(climatology: Any) -> Any:
    """Plot baseline monthly temperature and precipitation seasonality."""
    plt, sns = _plot_libraries()
    _require_columns(
        climatology,
        (
            "city",
            "city_slug",
            "month",
            "baseline_temperature",
            "baseline_precipitation",
        ),
    )
    palette = _palette_for_city_names(climatology)
    figure, axes = plt.subplots(1, 2, figsize=(15, 5.5))

    sns.lineplot(
        data=climatology,
        x="month",
        y="baseline_temperature",
        hue="city",
        hue_order=_city_names_in_order(climatology),
        palette=palette,
        marker="o",
        ax=axes[0],
    )
    axes[0].set(
        title="Monthly mean temperature",
        xlabel="Month",
        ylabel="Temperature (°C)",
        xticks=range(1, 13),
    )

    sns.lineplot(
        data=climatology,
        x="month",
        y="baseline_precipitation",
        hue="city",
        hue_order=_city_names_in_order(climatology),
        palette=palette,
        marker="o",
        ax=axes[1],
        legend=False,
    )
    axes[1].set(
        title="Monthly precipitation total",
        xlabel="Month",
        ylabel="Precipitation (mm)",
        xticks=range(1, 13),
    )
    figure.suptitle("1961–1990 monthly climate normals")
    figure.tight_layout()
    return figure


def plot_annual_temperature(annual_data: Any) -> Any:
    """Plot annual mean temperature and its trailing 10-year average by city."""
    plt, _ = _plot_libraries()
    _require_columns(
        annual_data,
        ("city", "city_slug", "year", "temperature_mean", "temperature_rolling_mean"),
    )
    figure, axes = _city_facets(annual_data, figsize=(15, 10), sharey=False)
    for axis, (city_slug, group) in zip(axes, _city_groups(annual_data)):
        color = CITY_COLORS.get(city_slug, "#333333")
        axis.plot(group["year"], group["temperature_mean"], color=color, alpha=0.28, linewidth=1)
        axis.plot(
            group["year"],
            group["temperature_rolling_mean"],
            color=color,
            linewidth=2.4,
            label="10-year trailing mean",
        )
        axis.set_title(str(group["city"].iloc[0]))
        axis.set_xlabel("Year")
        axis.set_ylabel("Temperature (°C)")
        axis.legend(loc="upper left")
    figure.suptitle("Annual mean temperature and long-term evolution")
    figure.tight_layout()
    return figure


def plot_annual_temperature_anomalies(annual_data: Any) -> Any:
    """Plot annual anomalies relative to the 1961–1990 city baseline."""
    plt, _ = _plot_libraries()
    _require_columns(
        annual_data,
        ("city", "city_slug", "year", "temperature_anomaly", "anomaly_rolling_mean"),
    )
    figure, axes = _city_facets(annual_data, figsize=(15, 10), sharey=True)
    for axis, (_, group) in zip(axes, _city_groups(annual_data)):
        colors = ["#D55E00" if value >= 0 else "#0072B2" for value in group["temperature_anomaly"]]
        axis.bar(group["year"], group["temperature_anomaly"], color=colors, width=0.9)
        axis.plot(group["year"], group["anomaly_rolling_mean"], color="#222222", linewidth=2)
        axis.axhline(0, color="#222222", linewidth=0.8)
        axis.set_title(str(group["city"].iloc[0]))
        axis.set_xlabel("Year")
        axis.set_ylabel("Anomaly (°C)")
    figure.suptitle("Annual temperature anomalies relative to 1961–1990")
    figure.tight_layout()
    return figure


def plot_monthly_anomaly_heatmaps(monthly_anomalies: Any) -> Any:
    """Create one year-by-month temperature-anomaly heatmap per city."""
    plt, sns = _plot_libraries()
    _require_columns(
        monthly_anomalies,
        ("city", "city_slug", "year", "month", "temperature_anomaly"),
    )
    figure, axes = _city_facets(monthly_anomalies, figsize=(16, 15), sharey=False)
    image = None
    for axis, (_, group) in zip(axes, _city_groups(monthly_anomalies)):
        matrix = group.pivot(index="year", columns="month", values="temperature_anomaly")
        image = sns.heatmap(
            matrix,
            cmap="RdBu_r",
            center=0,
            vmin=-4,
            vmax=4,
            cbar=False,
            xticklabels=["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"],
            yticklabels=10,
            ax=axis,
        )
        axis.set_title(str(group["city"].iloc[0]))
        axis.set_xlabel("Month")
        axis.set_ylabel("Year")

    if image is not None:
        colorbar_axis = figure.add_axes([0.92, 0.22, 0.015, 0.56])
        colorbar = figure.colorbar(
            image.collections[0],
            cax=colorbar_axis,
        )
        colorbar.set_label("Temperature anomaly (°C)")
    figure.suptitle("Monthly temperature anomalies relative to 1961–1990")
    figure.subplots_adjust(top=0.94, right=0.88, hspace=0.28, wspace=0.18)
    return figure


def plot_temperature_trends(trends: Any) -> Any:
    """Compare descriptive warming slopes across cities."""
    plt, sns = _plot_libraries()
    _require_columns(trends, ("city", "slope_celsius_per_decade"))
    ordered = trends.sort_values("slope_celsius_per_decade", ascending=True)
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
    axis.axvline(0, color="#222222", linewidth=0.9)
    axis.set(
        title="Exploratory linear warming rate, 1940–2025",
        xlabel="Temperature change (°C per decade)",
        ylabel="",
    )
    figure.tight_layout()
    return figure


def plot_extreme_heat_indicators(annual_data: Any) -> Any:
    """Plot hot days, tropical nights and heatwave days by city and year."""
    plt, _ = _plot_libraries()
    _require_columns(
        annual_data,
        ("city", "city_slug", "year", "hot_days", "tropical_nights", "heatwave_days"),
    )
    figure, axes = _city_facets(annual_data, figsize=(15, 10), sharey=False)
    for axis, (_, group) in zip(axes, _city_groups(annual_data)):
        axis.plot(group["year"], group["hot_days"], label="Days ≥ 30 °C", color="#E69F00", alpha=0.8)
        axis.plot(group["year"], group["tropical_nights"], label="Nights ≥ 20 °C", color="#CC79A7", alpha=0.8)
        axis.plot(group["year"], group["heatwave_days"], label="Heatwave days", color="#D55E00", alpha=0.8)
        axis.set_title(str(group["city"].iloc[0]))
        axis.set_xlabel("Year")
        axis.set_ylabel("Number of days")
        axis.legend(loc="upper left", fontsize=8)
    figure.suptitle("Evolution of extreme-heat indicators")
    figure.tight_layout()
    return figure


def plot_precipitation_indicators(annual_data: Any) -> Any:
    """Plot annual precipitation totals and heavy-rain frequency by city."""
    plt, _ = _plot_libraries()
    _require_columns(
        annual_data,
        (
            "city",
            "city_slug",
            "year",
            "precipitation_total",
            "precipitation_rolling_mean",
            "heavy_rain_days",
        ),
    )
    figure, axes = _city_facets(annual_data, figsize=(15, 10), sharey=False)
    for axis, (city_slug, group) in zip(axes, _city_groups(annual_data)):
        color = CITY_COLORS.get(city_slug, "#333333")
        axis.plot(group["year"], group["precipitation_total"], color=color, alpha=0.25, linewidth=1)
        axis.plot(group["year"], group["precipitation_rolling_mean"], color=color, linewidth=2.2)
        secondary = axis.twinx()
        secondary.plot(
            group["year"],
            group["heavy_rain_days"],
            color="#222222",
            alpha=0.45,
            linewidth=0.9,
        )
        axis.set_title(str(group["city"].iloc[0]))
        axis.set_xlabel("Year")
        axis.set_ylabel("Annual precipitation (mm)")
        secondary.set_ylabel("Heavy-rain days", color="#444444")
    figure.suptitle("Annual precipitation and days with at least 20 mm")
    figure.tight_layout()
    return figure


def _city_groups(data: Any) -> list[tuple[str, Any]]:
    """Return city groups in their first-occurrence order."""
    present = list(data["city_slug"].drop_duplicates())
    order = [city_slug for city_slug in CITY_COLORS if city_slug in present]
    order.extend(city_slug for city_slug in present if city_slug not in order)
    return [(city_slug, data.loc[data["city_slug"] == city_slug].sort_values("year")) for city_slug in order]


def _city_facets(data: Any, *, figsize: tuple[float, float], sharey: bool) -> tuple[Any, Any]:
    """Create a two-column grid sized for the cities present in a dataset."""
    plt, _ = _plot_libraries()
    city_count = data["city_slug"].nunique()
    if city_count == 0:
        raise ValueError("Cannot plot an empty city dataset.")
    columns = 2
    rows = (city_count + columns - 1) // columns
    figure, axes = plt.subplots(rows, columns, figsize=figsize, sharey=sharey, squeeze=False)
    flat_axes = axes.ravel()
    for axis in flat_axes[city_count:]:
        axis.set_visible(False)
    return figure, flat_axes[:city_count]


def _city_names_in_order(data: Any) -> list[str]:
    """Return display names in first-occurrence city order."""
    cities = data[["city_slug", "city"]].drop_duplicates().set_index("city_slug")["city"]
    order = [city_slug for city_slug in CITY_COLORS if city_slug in cities.index]
    order.extend(city_slug for city_slug in cities.index if city_slug not in order)
    return [str(cities.loc[city_slug]) for city_slug in order]


def _palette_for_city_names(data: Any) -> dict[str, str]:
    """Map display names to the stable slug-based color palette."""
    cities = data[["city_slug", "city"]].drop_duplicates()
    return {
        str(row.city): CITY_COLORS.get(str(row.city_slug), "#777777")
        for row in cities.itertuples(index=False)
    }


def _require_columns(data: Any, columns: Iterable[str]) -> None:
    """Raise a clear error when plotting input lacks required columns."""
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Plotting data is missing required columns: {missing}.")


def _plot_libraries() -> tuple[Any, Any]:
    """Import Matplotlib and Seaborn with a project-specific installation hint."""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "matplotlib and seaborn are required for EDA plots. Install requirements.txt."
        ) from exc
    return plt, sns
