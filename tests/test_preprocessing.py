"""Tests for cleaning and quality-report behavior."""

import importlib.util
import unittest
from datetime import date


PANDAS_AVAILABLE = importlib.util.find_spec("pandas") is not None


@unittest.skipUnless(PANDAS_AVAILABLE, "pandas is not installed")
class PreprocessingTests(unittest.TestCase):
    """Validate explicit missing-value policies and physical checks."""

    def setUp(self) -> None:
        """Create two complete dates with one known precipitation boundary gap."""
        import pandas as pd

        self.data = pd.DataFrame(
            {
                "city": ["Test City", "Test City"],
                "city_slug": ["test-city", "test-city"],
                "requested_latitude": [45.0, 45.0],
                "requested_longitude": [9.0, 9.0],
                "grid_latitude": [45.0, 45.0],
                "grid_longitude": [9.0, 9.0],
                "grid_elevation": [100.0, 100.0],
                "date": pd.to_datetime(["1940-01-01", "1940-01-02"]),
                "temperature_2m_mean": [2.0, 3.0],
                "temperature_2m_max": [5.0, 6.0],
                "temperature_2m_min": [-1.0, 0.0],
                "precipitation_sum": [float("nan"), 2.5],
            }
        )

    def test_documented_boundary_gap_is_allowed(self) -> None:
        """A declared date-column exception should remain visible but valid."""
        from scripts.preprocessing import build_quality_report

        report = build_quality_report(
            self.data,
            expected_city_slugs=["test-city"],
            start_date=date(1940, 1, 1),
            end_date=date(1940, 1, 2),
            allowed_missing_values={"precipitation_sum": {date(1940, 1, 1)}},
        )

        self.assertTrue(report.is_valid)
        self.assertEqual(report.allowed_null_counts["precipitation_sum"], 1)
        self.assertEqual(report.null_counts["precipitation_sum"], 0)

    def test_undeclared_missing_value_fails_validation(self) -> None:
        """The same missing value must fail without an explicit policy."""
        from scripts.preprocessing import build_quality_report

        report = build_quality_report(
            self.data,
            expected_city_slugs=["test-city"],
            start_date=date(1940, 1, 1),
            end_date=date(1940, 1, 2),
        )

        self.assertFalse(report.is_valid)
        self.assertEqual(report.null_counts["precipitation_sum"], 1)

    def test_invalid_temperature_order_fails_validation(self) -> None:
        """A daily mean above the maximum must be reported as invalid."""
        from scripts.preprocessing import build_quality_report

        self.data.loc[1, "temperature_2m_mean"] = 9.0
        report = build_quality_report(
            self.data,
            expected_city_slugs=["test-city"],
            start_date=date(1940, 1, 1),
            end_date=date(1940, 1, 2),
            allowed_missing_values={"precipitation_sum": {date(1940, 1, 1)}},
        )

        self.assertFalse(report.is_valid)
        self.assertEqual(len(report.invalid_temperature_rows), 1)


if __name__ == "__main__":
    unittest.main()
