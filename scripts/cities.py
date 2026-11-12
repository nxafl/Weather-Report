"""City catalogue used by the Italian climate comparison."""

from __future__ import annotations

from collections.abc import Iterable

from scripts.models import City


ITALIAN_CITIES: dict[str, City] = {
    "milan": City(
        name="Milan",
        slug="milan",
        latitude=45.4642,
        longitude=9.1900,
        region="Northern Italy and Po Valley",
    ),
    "turin": City(
        name="Turin",
        slug="turin",
        latitude=45.0703,
        longitude=7.6869,
        region="Northwestern Italy and Alpine influence",
    ),
    "rome": City(
        name="Rome",
        slug="rome",
        latitude=41.9028,
        longitude=12.4964,
        region="Central Italy",
    ),
    "bari": City(
        name="Bari",
        slug="bari",
        latitude=41.1171,
        longitude=16.8719,
        region="Southern Adriatic coast",
    ),
    "palermo": City(
        name="Palermo",
        slug="palermo",
        latitude=38.1157,
        longitude=13.3615,
        region="Southern Mediterranean climate",
    ),
    "cagliari": City(
        name="Cagliari",
        slug="cagliari",
        latitude=39.2238,
        longitude=9.1217,
        region="Insular and maritime climate",
    ),
}
"""Mapping of city slugs to the locations selected in the project plan."""


def get_cities(slugs: Iterable[str] | None = None) -> list[City]:
    """Return all project cities or a selected subset.

    Parameters
    ----------
    slugs:
        Iterable of city identifiers such as ``["milan", "rome"]``. When
        omitted, all configured cities are returned in catalogue order.

    Returns
    -------
    list of City
        Independent list containing the selected city objects.

    Raises
    ------
    KeyError
        If one or more requested slugs are not present in the catalogue.
    """
    if slugs is None:
        return list(ITALIAN_CITIES.values())

    selected_slugs = list(slugs)
    unknown = [slug for slug in selected_slugs if slug not in ITALIAN_CITIES]
    if unknown:
        available = ", ".join(ITALIAN_CITIES)
        raise KeyError(f"Unknown city slugs {unknown}. Available cities: {available}.")
    return [ITALIAN_CITIES[slug] for slug in selected_slugs]
