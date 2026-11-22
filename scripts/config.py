"""Project settings shared by the data and analysis notebooks."""


START_DATE = "1940-01-01"
END_DATE = "2025-12-31"
TIMEZONE = "Europe/Rome"

DAILY_VARIABLES = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
]

CITIES = [
    {"name": "Milan", "slug": "milan", "latitude": 45.4642, "longitude": 9.1900},
    {"name": "Turin", "slug": "turin", "latitude": 45.0703, "longitude": 7.6869},
    {"name": "Rome", "slug": "rome", "latitude": 41.9028, "longitude": 12.4964},
    {"name": "Bari", "slug": "bari", "latitude": 41.1171, "longitude": 16.8719},
    {"name": "Palermo", "slug": "palermo", "latitude": 38.1157, "longitude": 13.3615},
    {"name": "Cagliari", "slug": "cagliari", "latitude": 39.2238, "longitude": 9.1217},
]
