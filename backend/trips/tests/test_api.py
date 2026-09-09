"""API tests. Geocoding and routing are stubbed so tests never hit the network."""

import pytest

from trips.services import geocode as geocode_mod
from trips.services import routing as routing_mod
from trips.services.geocode import Place
from trips.services.routing import Leg, Route

pytestmark = pytest.mark.django_db

_PLACES = {
    "joplin, mo": Place("Joplin, MO", 37.084, -94.513, "Joplin, Jasper County, Missouri, USA"),
    "council bluffs, ia": Place("Council Bluffs, IA", 41.261, -95.860, "Council Bluffs, Pottawattamie County, Iowa, USA"),
    "st. louis, mo": Place("St. Louis, MO", 38.627, -90.199, "St. Louis, Missouri, USA"),
}


@pytest.fixture(autouse=True)
def stub_external(monkeypatch):
    def fake_geocode(addr):
        try:
            return _PLACES[" ".join(addr.split()).lower()]
        except KeyError:
            raise geocode_mod.GeocodeError(f"no match for {addr!r}")

    def fake_route(points):
        legs = [Leg(180.0, 3.0), Leg(290.0, 5.0)][: len(points) - 1]
        return Route(
            distance_mi=sum(l.distance_mi for l in legs),
            duration_h=sum(l.duration_h for l in legs),
            legs=legs,
            geometry=[points[0], points[-1]],
        )

    monkeypatch.setattr("trips.services.planner.geocode.geocode", fake_geocode)
    monkeypatch.setattr("trips.services.planner.geocode.reverse", lambda lat, lon: "Somewhere, ST")
    monkeypatch.setattr("trips.services.planner.routing.route", fake_route)


def _body(**over):
    body = {
        "current_location": "Joplin, MO",
        "pickup_location": "Council Bluffs, IA",
        "dropoff_location": "St. Louis, MO",
        "current_cycle_used_h": 10,
    }
    body.update(over)
    return body


def test_create_trip_returns_full_plan(client):
    r = client.post("/api/trips", data=_body(), content_type="application/json")
    assert r.status_code == 201, r.content
    data = r.json()
    assert data["id"]
    assert data["summary"]["total_miles"] == 470.0
    assert data["log_days"] and all(d["totals"]["total"] == "24:00" for d in data["log_days"])
    assert data["compliance"]["ok"] is True
    assert data["timeline"][0]["label"] == "Pre-trip inspection"
    assert data["timeline"][-1]["label"] == "Post-trip inspection"
    assert any(s["kind"] == "Pickup" for s in data["stops"])


def test_trip_is_listed_in_history(client):
    client.post("/api/trips", data=_body(), content_type="application/json")
    r = client.get("/api/trips")
    assert r.status_code == 200
    assert r.json()["count"] == 1
    row = r.json()["results"][0]
    assert row["pickup_location"] == "Council Bluffs, IA"
    assert row["total_days"] >= 1


def test_get_trip_by_id(client):
    created = client.post("/api/trips", data=_body(), content_type="application/json").json()
    r = client.get(f"/api/trips/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["log_days"] == created["log_days"]


def test_cycle_over_70_is_rejected(client):
    r = client.post("/api/trips", data=_body(current_cycle_used_h=75), content_type="application/json")
    assert r.status_code == 400


def test_unknown_address_returns_422(client):
    r = client.post("/api/trips", data=_body(current_location="Atlantis"), content_type="application/json")
    assert r.status_code == 422
    assert "Could not locate" in r.json()["error"]


def test_header_fields_round_trip(client):
    r = client.post(
        "/api/trips",
        data=_body(carrier_name="Acme Freight", tractor_number="T-42", commodity="Paper"),
        content_type="application/json",
    )
    assert r.status_code == 201
    assert r.json()["header"]["carrier_name"] == "Acme Freight"
    assert r.json()["header"]["tractor_number"] == "T-42"


def test_missing_departure_defaults_to_now(client):
    r = client.post("/api/trips", data=_body(), content_type="application/json")
    assert r.status_code == 201
    assert r.json()["input"]["departure_at"]


def test_split_sleeper_flag_is_honored(client):
    r = client.post(
        "/api/trips",
        data=_body(current_cycle_used_h=0, use_split_sleeper=True, dropoff_location="St. Louis, MO"),
        content_type="application/json",
    )
    assert r.status_code == 201
    assert r.json()["input"]["use_split_sleeper"] is True
