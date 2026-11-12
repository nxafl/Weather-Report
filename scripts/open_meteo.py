"""Functions for downloading historical ERA5 data from Open-Meteo."""

from __future__ import annotations

import csv
import json
import time
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.models import (
    DEFAULT_DAILY_VARIABLES,
    ArchiveRequest,
    City,
    WeatherDataset,
)


ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
"""Base URL of the Open-Meteo Historical Weather API."""

RETRYABLE_HTTP_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
"""HTTP response codes for which a request may safely be retried."""

MIN_RATE_LIMIT_DELAY = 60.0
"""Minimum wait before retrying a request rejected by the minute limit."""


class OpenMeteoError(RuntimeError):
    """Raised when an Open-Meteo request or response cannot be processed."""


def build_archive_url(request: ArchiveRequest) -> str:
    """Build the complete Open-Meteo archive URL for a request.

    Parameters
    ----------
    request:
        Validated archive request.

    Returns
    -------
    str
        URL containing encoded coordinates, dates, variables, time zone and
        ERA5 model selection.

    Notes
    -----
    This function performs no network operation, which makes it useful for
    inspecting and documenting requests inside a notebook.
    """
    return f"{ARCHIVE_API_URL}?{urlencode(request.to_query_params())}"


def fetch_city_weather(
    city: City,
    start_date: date = date(1940, 1, 1),
    end_date: date = date(2025, 12, 31),
    daily_variables: Iterable[str] = DEFAULT_DAILY_VARIABLES,
    *,
    timeout: float = 60.0,
    max_retries: int = 5,
    retry_delay: float = 1.0,
) -> WeatherDataset:
    """Download and validate historical daily ERA5 data for one city.

    Parameters
    ----------
    city:
        City to request.
    start_date, end_date:
        Inclusive download period. Defaults match the project plan.
    daily_variables:
        Iterable of Open-Meteo daily variable names.
    timeout:
        Maximum number of seconds to wait for each HTTP attempt.
    max_retries:
        Number of retries after the initial attempt for temporary network or
        server failures. Set to zero to disable retries.
    retry_delay:
        Initial delay in seconds. Subsequent retries use exponential backoff.
        HTTP 429 responses follow the server's ``Retry-After`` header or wait
        at least 60 seconds when that header is absent.

    Returns
    -------
    WeatherDataset
        Validated response with both raw and row-oriented access to the data.

    Raises
    ------
    ValueError
        If request parameters are invalid.
    OpenMeteoError
        If the server cannot be reached, rejects the request, returns invalid
        JSON or returns a structurally invalid response.

    Examples
    --------
    >>> from scripts.cities import ITALIAN_CITIES
    >>> dataset = fetch_city_weather(ITALIAN_CITIES["milan"])
    >>> len(dataset) > 30_000
    True
    """
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero.")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative.")
    if retry_delay < 0:
        raise ValueError("retry_delay cannot be negative.")

    archive_request = ArchiveRequest(
        city=city,
        start_date=start_date,
        end_date=end_date,
        daily_variables=tuple(daily_variables),
    )
    payload = _fetch_json(
        build_archive_url(archive_request),
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )

    try:
        return WeatherDataset.from_api_response(archive_request, payload)
    except (TypeError, ValueError) as exc:
        raise OpenMeteoError(f"Invalid Open-Meteo response: {exc}") from exc


def fetch_multiple_cities(
    cities: Iterable[City],
    start_date: date = date(1940, 1, 1),
    end_date: date = date(2025, 12, 31),
    daily_variables: Iterable[str] = DEFAULT_DAILY_VARIABLES,
    *,
    timeout: float = 60.0,
    max_retries: int = 5,
    retry_delay: float = 1.0,
) -> dict[str, WeatherDataset]:
    """Download the same historical variables for several cities.

    Parameters
    ----------
    cities:
        Iterable of locations. Downloads run sequentially to keep API usage
        predictable and make failures easy to identify.
    start_date, end_date:
        Inclusive period shared by all cities.
    daily_variables:
        Variables shared by all requests.
    timeout, max_retries, retry_delay:
        Network settings passed to :func:`fetch_city_weather`.

    Returns
    -------
    dict
        Mapping from city slug to its validated dataset.

    Raises
    ------
    ValueError
        If city slugs are duplicated or no city is supplied.
    OpenMeteoError
        If any individual city download fails. Previously downloaded results
        remain only in memory and are not written automatically.
    """
    city_list = list(cities)
    if not city_list:
        raise ValueError("At least one city is required.")
    slugs = [city.slug for city in city_list]
    if len(slugs) != len(set(slugs)):
        raise ValueError("City slugs must be unique.")

    variables = tuple(daily_variables)
    return {
        city.slug: fetch_city_weather(
            city,
            start_date=start_date,
            end_date=end_date,
            daily_variables=variables,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        for city in city_list
    }


def save_response_json(
    dataset: WeatherDataset,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Save the untouched decoded API response as formatted JSON.

    Parameters
    ----------
    dataset:
        Dataset whose original response should be preserved.
    path:
        Destination file. Missing parent directories are created.
    overwrite:
        When ``False`` (default), refuse to replace an existing file.

    Returns
    -------
    pathlib.Path
        Resolved destination path.

    Raises
    ------
    FileExistsError
        If the destination exists and ``overwrite`` is false.
    """
    destination = _prepare_destination(path, overwrite=overwrite)
    _atomic_write_text(
        destination,
        json.dumps(dataset.raw_payload, ensure_ascii=False, indent=2) + "\n",
    )
    return destination


def save_records_csv(
    dataset: WeatherDataset,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Save normalized daily observations as a UTF-8 CSV file.

    Parameters
    ----------
    dataset:
        Validated dataset to convert to row-oriented records.
    path:
        Destination CSV file. Missing parent directories are created.
    overwrite:
        When ``False`` (default), refuse to replace an existing file.

    Returns
    -------
    pathlib.Path
        Resolved destination path.

    Raises
    ------
    FileExistsError
        If the destination exists and ``overwrite`` is false.
    ValueError
        If the dataset contains no records.
    """
    destination = _prepare_destination(path, overwrite=overwrite)
    records = dataset.iter_records()
    try:
        first_record = next(records)
    except StopIteration as exc:
        raise ValueError("Cannot save an empty weather dataset.") from exc

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=list(first_record))
            writer.writeheader()
            writer.writerow(first_record)
            writer.writerows(records)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _fetch_json(
    url: str,
    *,
    timeout: float,
    max_retries: int,
    retry_delay: float,
) -> Mapping[str, Any]:
    """Fetch a JSON mapping with retries for temporary failures."""
    request = Request(
        url,
        headers={"User-Agent": "Weather-Report educational project/1.0"},
    )

    for attempt in range(max_retries + 1):
        wait_seconds = retry_delay * (2**attempt)
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, Mapping):
                raise OpenMeteoError("Open-Meteo returned a non-object JSON response.")
            return payload
        except HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == max_retries:
                reason = _read_http_error_reason(exc)
                raise OpenMeteoError(
                    f"Open-Meteo HTTP {exc.code}: {reason}"
                ) from exc
            if exc.code == 429:
                wait_seconds = _rate_limit_wait_seconds(exc, wait_seconds)
                warnings.warn(
                    "Open-Meteo minute limit reached. "
                    f"Retrying automatically in {wait_seconds:g} seconds.",
                    RuntimeWarning,
                    stacklevel=2,
                )
        except (URLError, TimeoutError) as exc:
            if attempt == max_retries:
                raise OpenMeteoError(
                    f"Could not reach Open-Meteo after {attempt + 1} attempts: {exc}"
                ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OpenMeteoError("Open-Meteo returned invalid JSON.") from exc

        time.sleep(wait_seconds)

    raise AssertionError("Retry loop ended unexpectedly.")


def _read_http_error_reason(error: HTTPError) -> str:
    """Extract a useful error message from an HTTP error response."""
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return str(error.reason)
    if isinstance(payload, Mapping):
        return str(payload.get("reason", error.reason))
    return str(error.reason)


def _rate_limit_wait_seconds(error: HTTPError, fallback: float) -> float:
    """Return the server-requested delay for an HTTP 429 response.

    Open-Meteo may provide a numeric ``Retry-After`` header. Invalid, missing
    or shorter values fall back to at least one minute, matching the API's
    minute-limit error guidance.
    """
    retry_after = error.headers.get("Retry-After") if error.headers else None
    try:
        server_delay = float(retry_after) if retry_after is not None else 0.0
    except ValueError:
        server_delay = 0.0
    return max(MIN_RATE_LIMIT_DELAY, fallback, server_delay)


def _prepare_destination(path: str | Path, *, overwrite: bool) -> Path:
    """Resolve a destination, create its parent, and enforce overwrite policy."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Destination already exists: {destination}. "
            "Pass overwrite=True to replace it."
        )
    return destination


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text through a temporary sibling and atomically replace the target."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
