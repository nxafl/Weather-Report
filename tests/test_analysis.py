"""Tests for exploratory climate feature engineering and indicators."""

import importlib.util
import unittest


PANDAS_AVAILABLE = importlib.util.find_spec("pandas") is not None


@unittest.skipUnless(PANDAS_AVAILABLE, "pandas is not installed")
class AnalysisTests(unittest.TestCase):
    """Exercise calendar, annual, anomaly and heatwave calculations."""

    @staticmethod
    def _daily_frame(dates, maximums, precipitation=None):
        """Build the minimum valid daily DataFrame required by analysis functions."""
        import pandas as pd

        precipitation = precipitation if precipitation is not None else [0.0] * len(dates)
        return pd.DataFrame(
            {
                "city": ["Test City"] * len(dates),
                "city_slug": ["test-city"] * len(dates),
                "date": pd.to_datetime(dates),
                "temperature_2m_mean": [value - 5 for value in maximums],
                "temperature_2m_max": maximums,
                "temperature_2m_min": [value - 10 for value in maximums],
                "precipitation_sum": precipitation,
            }
        )

    def test_december_uses_following_season_year(self) -> None:
        """December must be grouped with the following January and February."""
        from scripts.analysis import add_calendar_features

        data = self._daily_frame(["2020-12-15", "2021-01-15"], [12.0, 10.0])
        featured = add_calendar_features(data)

        self.assertEqual(featured["season"].astype(str).tolist(), ["Winter", "Winter"])
        self.assertEqual(featured["season_year"].tolist(), [2021, 2021])

    def test_incomplete_precipitation_year_is_not_summed(self) -> None:
        """A missing daily precipitation value must invalidate annual rain metrics."""
        from scripts.analysis import add_calendar_features, calculate_annual_indicators

        data = self._daily_frame(
            ["1940-01-01", "1940-01-02"],
            [10.0, 11.0],
            [float("nan"), 5.0],
        )
        annual = calculate_annual_indicators(add_calendar_features(data))

        self.assertTrue(annual.loc[0, "precipitation_total"] != annual.loc[0, "precipitation_total"])
        self.assertEqual(annual.loc[0, "precipitation_missing_days"], 1)
        self.assertAlmostEqual(annual.loc[0, "temperature_max_mean"], 10.5)
        self.assertAlmostEqual(annual.loc[0, "temperature_min_mean"], 0.5)
        self.assertAlmostEqual(annual.loc[0, "diurnal_temperature_range"], 10.0)

    def test_heatwave_requires_three_consecutive_days(self) -> None:
        """Four consecutive recent exceedances should form one four-day heatwave."""
        from scripts.analysis import add_calendar_features, calculate_heatwave_indicators

        dates = []
        maximums = []
        for year in range(2000, 2020):
            dates.extend([f"{year}-07-01", f"{year}-07-02", f"{year}-07-03"])
            maximums.extend([20.0, 25.0, 30.0])
        dates.extend(["2020-07-01", "2020-07-02", "2020-07-03", "2020-07-04"])
        maximums.extend([40.0, 41.0, 42.0, 43.0])

        data = add_calendar_features(self._daily_frame(dates, maximums))
        _, indicators = calculate_heatwave_indicators(
            data,
            baseline_start=2000,
            baseline_end=2019,
        )
        recent = indicators.loc[indicators["year"] == 2020].iloc[0]

        self.assertEqual(recent["heatwave_count"], 1)
        self.assertEqual(recent["heatwave_days"], 4)
        self.assertEqual(recent["maximum_heatwave_duration"], 4)

    def test_period_comparison_calculates_absolute_change(self) -> None:
        """Period comparison should subtract the early mean from the recent mean."""
        import pandas as pd
        from scripts.analysis import compare_climate_periods

        annual = pd.DataFrame(
            {
                "city": ["Test City"] * 4,
                "city_slug": ["test-city"] * 4,
                "year": [1941, 1942, 2000, 2001],
                "temperature_mean": [10.0, 12.0, 14.0, 16.0],
            }
        )
        comparison = compare_climate_periods(
            annual,
            metrics=["temperature_mean"],
            early_period=(1941, 1942),
            recent_period=(2000, 2001),
        )

        self.assertEqual(comparison.loc[0, "early_mean"], 11.0)
        self.assertEqual(comparison.loc[0, "recent_mean"], 15.0)
        self.assertEqual(comparison.loc[0, "absolute_change"], 4.0)


if __name__ == "__main__":
    unittest.main()
