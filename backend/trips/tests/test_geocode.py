"""geocode() should prefer Photon and fall back to Nominatim. No network here."""

from trips.services import geocode
from trips.services.geocode import GeocodeError, Place

import pytest


@pytest.fixture(autouse=True)
def clear_cache():
    geocode._cache.clear()
    yield
    geocode._cache.clear()


def test_photon_hit_is_used(monkeypatch):
    monkeypatch.setattr(geocode, "_photon_lookup", lambda a: Place(a, 39.1, -94.6, "Photon Place"))
    monkeypatch.setattr(geocode, "_nominatim_lookup", lambda a: pytest.fail("should not reach Nominatim"))
    got = geocode.geocode("Scott Joplin House, Saint Louis, Missouri")
    assert (got.lat, got.lon, got.display_name) == (39.1, -94.6, "Photon Place")


def test_falls_back_to_nominatim_when_photon_misses(monkeypatch):
    monkeypatch.setattr(geocode, "_photon_lookup", lambda a: None)
    monkeypatch.setattr(geocode, "_nominatim_lookup", lambda a: Place(a, 1.0, 2.0, "Nominatim Place"))
    assert geocode.geocode("Saint John Church, Kansas").display_name == "Nominatim Place"


def test_falls_back_when_photon_raises(monkeypatch):
    def boom(_a):
        raise ValueError("bad json")

    monkeypatch.setattr(geocode, "_photon_lookup", boom)
    monkeypatch.setattr(geocode, "_nominatim_lookup", lambda a: Place(a, 3.0, 4.0, "fallback"))
    assert geocode.geocode("somewhere odd").lat == 3.0


def test_raises_when_both_miss(monkeypatch):
    monkeypatch.setattr(geocode, "_photon_lookup", lambda a: None)

    def no_match(a):
        raise GeocodeError(f"no match for {a!r}")

    monkeypatch.setattr(geocode, "_nominatim_lookup", no_match)
    with pytest.raises(GeocodeError):
        geocode.geocode("Atlantis")
