"""Tests for inferential climate trend models."""

import importlib.util
import unittest


DEPENDENCIES_AVAILABLE = all(
    importlib.util.find_spec(package) is not None
    for package in ("numpy", "pandas", "statsmodels")
)


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "statistical dependencies are not installed")
class StatisticalAnalysisTests(unittest.TestCase):
    """Validate trend units, seasonal completeness and city interactions."""

    def test_grouped_trend_is_reported_per_decade(self) -> None:
        """A 0.2 °C/year series should be reported as 2 °C/decade."""
        import pandas as pd
        from scripts.statistical_analysis import fit_grouped_linear_trends

        years = list(range(2000, 2020))
        data = pd.DataFrame(
            {
                "city": ["Test City"] * len(years),
                "city_slug": ["test-city"] * len(years),
                "year": years,
                "temperature_mean": [10 + 0.2 * (year - 2000) for year in years],
            }
        )
        result = fit_grouped_linear_trends(data, "temperature_mean")

        self.assertAlmostEqual(result.loc[0, "slope_per_decade"], 2.0, places=8)
        self.assertEqual(result.loc[0, "observations"], 20)

    def test_seasonal_aggregation_removes_partial_winter(self) -> None:
        """A January-February boundary winter must not be treated as complete."""
        import pandas as pd
        from scripts.analysis import add_calendar_features
        from scripts.statistical_analysis import calculate_seasonal_indicators

        dates = pd.to_datetime(
            ["1940-01-15", "1940-02-15", "1940-03-15", "1940-04-15", "1940-05-15"]
        )
        data = pd.DataFrame(
            {
                "city": ["Test City"] * len(dates),
                "city_slug": ["test-city"] * len(dates),
                "date": dates,
                "temperature_2m_mean": [5.0, 6.0, 10.0, 12.0, 15.0],
                "temperature_2m_max": [8.0, 9.0, 14.0, 16.0, 19.0],
                "temperature_2m_min": [2.0, 3.0, 6.0, 8.0, 11.0],
                "precipitation_sum": [1.0] * len(dates),
            }
        )
        seasonal = calculate_seasonal_indicators(add_calendar_features(data))

        self.assertEqual(len(seasonal), 1)
        self.assertEqual(str(seasonal.loc[0, "season"]), "Spring")

    def test_interaction_model_recovers_city_slopes(self) -> None:
        """The interaction model should recover different synthetic city slopes."""
        import pandas as pd
        from scripts.statistical_analysis import fit_city_year_interaction

        rows = []
        for city, slug, slope in (("Alpha", "alpha", 0.1), ("Beta", "beta", 0.3)):
            for year in range(2000, 2020):
                rows.append(
                    {
                        "city": city,
                        "city_slug": slug,
                        "year": year,
                        "temperature_mean": 10 + slope * (year - 2000),
                    }
                )
        result = fit_city_year_interaction(
            pd.DataFrame(rows),
            reference_city_slug="alpha",
        )
        slopes = result.city_slopes.set_index("city_slug")["slope_per_decade"]

        self.assertAlmostEqual(slopes["alpha"], 1.0, places=8)
        self.assertAlmostEqual(slopes["beta"], 3.0, places=8)
        self.assertAlmostEqual(
            result.interaction_effects.loc[0, "slope_difference_per_decade"],
            2.0,
            places=8,
        )


if __name__ == "__main__":
    unittest.main()
