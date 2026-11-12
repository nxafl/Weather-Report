"""Unit tests for the weather data models and serialization helpers."""

import json
import tempfile
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.cities import ITALIAN_CITIES, get_cities
from scripts.models import ArchiveRequest, WeatherDataset
from scripts.open_meteo import (
    build_archive_url,
    fetch_city_weather,
    save_records_csv,
    save_response_json,
)


class WeatherModelTests(unittest.TestCase):
    """Test model validation without making external API requests."""

    def setUp(self) -> None:
        """Create a small valid request and representative API response."""
        self.request = ArchiveRequest(
            city=ITALIAN_CITIES["milan"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 2),
        )
        self.payload = {
            "latitude": 45.5,
            "longitude": 9.25,
            "elevation": 122.0,
            "timezone": "Europe/Rome",
            "daily_units": {
                "time": "iso8601",
                "temperature_2m_mean": "°C",
                "temperature_2m_max": "°C",
                "temperature_2m_min": "°C",
                "precipitation_sum": "mm",
            },
            "daily": {
                "time": ["2020-01-01", "2020-01-02"],
                "temperature_2m_mean": [3.0, 4.0],
                "temperature_2m_max": [7.0, 8.0],
                "temperature_2m_min": [-1.0, 0.0],
                "precipitation_sum": [0.0, 2.5],
            },
        }

    def test_build_url_contains_era5_and_dates(self) -> None:
        """The generated URL should include the core reproducibility fields."""
        url = build_archive_url(self.request)
        self.assertIn("models=era5", url)
        self.assertIn("start_date=2020-01-01", url)
        self.assertIn("end_date=2020-01-02", url)
        self.assertIn("temperature_2m_mean", url)

    def test_response_is_converted_to_records(self) -> None:
        """Column-oriented API values should become daily row dictionaries."""
        dataset = WeatherDataset.from_api_response(self.request, self.payload)
        records = dataset.to_records()
        self.assertEqual(len(dataset), 2)
        self.assertEqual(records[0]["city_slug"], "milan")
        self.assertEqual(records[1]["precipitation_sum"], 2.5)

    def test_mismatched_columns_are_rejected(self) -> None:
        """A partial daily column should fail validation before analysis."""
        self.payload["daily"]["temperature_2m_max"] = [7.0]
        with self.assertRaisesRegex(ValueError, "do not all match"):
            WeatherDataset.from_api_response(self.request, self.payload)

    def test_non_sequence_column_is_rejected(self) -> None:
        """Malformed scalar columns should produce a clear validation error."""
        self.payload["daily"]["temperature_2m_max"] = 7.0
        with self.assertRaisesRegex(ValueError, "not a sequence"):
            WeatherDataset.from_api_response(self.request, self.payload)

    def test_unknown_city_is_rejected(self) -> None:
        """Catalogue lookup should clearly report invalid city slugs."""
        with self.assertRaisesRegex(KeyError, "Unknown city"):
            get_cities(["not-a-city"])

    def test_json_and_csv_are_saved(self) -> None:
        """Serialization helpers should preserve JSON and produce two CSV rows."""
        dataset = WeatherDataset.from_api_response(self.request, self.payload)
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            json_path = save_response_json(dataset, directory / "weather.json")
            csv_path = save_records_csv(dataset, directory / "weather.csv")

            self.assertEqual(json.loads(json_path.read_text()), self.payload)
            self.assertEqual(len(csv_path.read_text().splitlines()), 3)

    def test_rate_limit_waits_one_minute_and_retries(self) -> None:
        """HTTP 429 should wait for the minute window before retrying."""
        rate_limit_error = HTTPError(
            url="https://example.test",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=BytesIO(b'{"error": true, "reason": "Minute limit exceeded"}'),
        )
        successful_response = BytesIO(json.dumps(self.payload).encode("utf-8"))

        with (
            patch(
                "scripts.open_meteo.urlopen",
                side_effect=[rate_limit_error, successful_response],
            ),
            patch("scripts.open_meteo.time.sleep") as mocked_sleep,
            patch("scripts.open_meteo.warnings.warn") as mocked_warning,
        ):
            dataset = fetch_city_weather(
                ITALIAN_CITIES["milan"],
                start_date=date(2020, 1, 1),
                end_date=date(2020, 1, 2),
                max_retries=1,
            )

        self.assertEqual(len(dataset), 2)
        mocked_sleep.assert_called_once_with(60.0)
        mocked_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
