"""Data models used to request and represent historical weather data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterator, Mapping, Sequence


DEFAULT_DAILY_VARIABLES: tuple[str, ...] = (
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
)
"""Daily Open-Meteo variables used by the core climate analysis."""


@dataclass(frozen=True, slots=True)
class City:
    """Geographical location for which weather data will be requested.

    Parameters
    ----------
    name:
        Human-readable city name used in tables and charts.
    slug:
        Stable lowercase identifier used in dictionaries and file names.
    latitude:
        WGS84 latitude in decimal degrees, between -90 and 90.
    longitude:
        WGS84 longitude in decimal degrees, between -180 and 180.
    region:
        Short description of the geographical area represented by the city.
    """

    name: str
    slug: str
    latitude: float
    longitude: float
    region: str = ""

    def __post_init__(self) -> None:
        """Validate the city identifier and geographical coordinates."""
        if not self.name.strip():
            raise ValueError("City name cannot be empty.")
        if not self.slug or not self.slug.replace("-", "").isalnum():
            raise ValueError("City slug must contain only letters, numbers or hyphens.")
        if self.slug != self.slug.lower():
            raise ValueError("City slug must be lowercase.")
        if not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        if not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees.")


@dataclass(frozen=True, slots=True)
class ArchiveRequest:
    """Validated parameters for one Open-Meteo archive request.

    Parameters
    ----------
    city:
        Location to download.
    start_date, end_date:
        Inclusive date range. ``end_date`` cannot precede ``start_date``.
    daily_variables:
        Names accepted by the Open-Meteo ``daily`` query parameter.
    model:
        Reanalysis model. The project fixes this to ``era5`` to preserve a
        consistent data source across the complete 1940-2025 period.
    timezone:
        IANA time-zone name used to define daily boundaries.
    """

    city: City
    start_date: date
    end_date: date
    daily_variables: tuple[str, ...] = DEFAULT_DAILY_VARIABLES
    model: str = "era5"
    timezone: str = "Europe/Rome"

    def __post_init__(self) -> None:
        """Validate dates and normalize the variable collection to a tuple."""
        object.__setattr__(self, "daily_variables", tuple(self.daily_variables))

        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date.")
        if not self.daily_variables:
            raise ValueError("At least one daily weather variable is required.")
        if len(set(self.daily_variables)) != len(self.daily_variables):
            raise ValueError("daily_variables cannot contain duplicates.")
        if any(not variable.strip() for variable in self.daily_variables):
            raise ValueError("Weather variable names cannot be empty.")
        if self.model.lower() != "era5":
            raise ValueError("This project requires the ERA5 model for consistency.")
        if not self.timezone.strip():
            raise ValueError("timezone cannot be empty.")

    def to_query_params(self) -> dict[str, str | float]:
        """Return parameters in the format required by the archive API.

        Returns
        -------
        dict
            URL-ready parameter names and values. Daily variables are encoded
            as a comma-separated string.
        """
        return {
            "latitude": self.city.latitude,
            "longitude": self.city.longitude,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "daily": ",".join(self.daily_variables),
            "timezone": self.timezone,
            "models": self.model,
        }


@dataclass(frozen=True, slots=True)
class WeatherDataset:
    """Validated weather response associated with its original request.

    The object retains the untouched API payload for reproducibility and also
    offers :meth:`iter_records`, which converts Open-Meteo's column-oriented
    JSON response into row-oriented dictionaries suitable for a DataFrame.

    Parameters
    ----------
    request:
        Request that produced the response.
    latitude, longitude:
        Coordinates of the grid cell selected by Open-Meteo.
    elevation:
        Elevation of the selected grid cell, in metres when provided.
    timezone:
        Time zone returned by the API.
    daily_units:
        Mapping from each daily variable to its unit.
    daily:
        Column-oriented daily values, including the ``time`` column.
    raw_payload:
        Complete decoded JSON object returned by the API.
    """

    request: ArchiveRequest
    latitude: float
    longitude: float
    elevation: float | None
    timezone: str
    daily_units: Mapping[str, str]
    daily: Mapping[str, Sequence[Any]]
    raw_payload: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_api_response(
        cls,
        request: ArchiveRequest,
        payload: Mapping[str, Any],
    ) -> "WeatherDataset":
        """Create and validate a dataset from a decoded Open-Meteo response.

        Parameters
        ----------
        request:
            Request associated with the response.
        payload:
            JSON response already decoded into a mapping.

        Returns
        -------
        WeatherDataset
            Validated response object.

        Raises
        ------
        ValueError
            If required fields are missing or daily columns have different
            lengths.
        """
        if payload.get("error"):
            reason = payload.get("reason", "Unknown Open-Meteo API error")
            raise ValueError(str(reason))

        daily = payload.get("daily")
        if not isinstance(daily, Mapping):
            raise ValueError("API response does not contain a valid 'daily' object.")

        time_values = daily.get("time")
        if not isinstance(time_values, Sequence) or isinstance(time_values, str):
            raise ValueError("API response does not contain a valid daily time column.")

        expected_columns = ("time", *request.daily_variables)
        missing = [column for column in expected_columns if column not in daily]
        if missing:
            raise ValueError(f"API response is missing daily columns: {missing}")

        expected_length = len(time_values)
        invalid_lengths: dict[str, int | str] = {}
        for column in expected_columns:
            values = daily[column]
            if not isinstance(values, Sequence) or isinstance(values, str):
                invalid_lengths[column] = "not a sequence"
            elif len(values) != expected_length:
                invalid_lengths[column] = len(values)
        if invalid_lengths:
            raise ValueError(
                "Daily columns do not all match the time column length: "
                f"{invalid_lengths}"
            )

        try:
            latitude = float(payload["latitude"])
            longitude = float(payload["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("API response has invalid grid-cell coordinates.") from exc

        elevation_value = payload.get("elevation")
        elevation = float(elevation_value) if elevation_value is not None else None
        daily_units = payload.get("daily_units", {})
        if not isinstance(daily_units, Mapping):
            raise ValueError("API response has an invalid 'daily_units' object.")

        return cls(
            request=request,
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
            timezone=str(payload.get("timezone", request.timezone)),
            daily_units=daily_units,
            daily=daily,
            raw_payload=payload,
        )

    def __len__(self) -> int:
        """Return the number of daily observations in the dataset."""
        return len(self.daily["time"])

    def iter_records(self) -> Iterator[dict[str, Any]]:
        """Yield one normalized dictionary per day.

        Every record contains the date, requested city details, returned grid
        coordinates and all requested daily variables. The result can be passed
        directly to ``pandas.DataFrame``.

        Yields
        ------
        dict
            One row-oriented daily weather observation.

        Examples
        --------
        >>> import pandas as pd
        >>> dataframe = pd.DataFrame(dataset.iter_records())
        """
        columns = ("time", *self.request.daily_variables)
        for index in range(len(self)):
            record: dict[str, Any] = {
                "city": self.request.city.name,
                "city_slug": self.request.city.slug,
                "requested_latitude": self.request.city.latitude,
                "requested_longitude": self.request.city.longitude,
                "grid_latitude": self.latitude,
                "grid_longitude": self.longitude,
                "grid_elevation": self.elevation,
            }
            record.update({column: self.daily[column][index] for column in columns})
            yield record

    def to_records(self) -> list[dict[str, Any]]:
        """Return all daily observations as a list of dictionaries.

        Returns
        -------
        list of dict
            Materialized row-oriented observations. For very large downloads,
            prefer :meth:`iter_records` to avoid an extra in-memory copy.
        """
        return list(self.iter_records())
