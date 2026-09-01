import pytest

from garmin_ssi import ssi_sites

# Real shape of a locationServices.php reply (trimmed).
FAKE_REPLY = {
    "stats": {"total": 2},
    "result": {
        "elements": [
            {"ident": "divesite", "data": {"properties": {
                "id": "1965", "name": "White Star Quarry",
                "lat": "41.3716", "lng": "-83.3155", "distanceToCenter": "2.03"}}},
            {"ident": "divesite", "data": {"properties": {
                "id": "9999", "name": "Far Away",
                "lat": "42.0", "lng": "-84.0", "distanceToCenter": "80"}}},
        ]
    },
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(ssi_sites._Locator, "__init__", lambda self, api_key=None: None)
    monkeypatch.setattr(ssi_sites._Locator, "query", lambda self, req: FAKE_REPLY)


def test_sites_near_sorted_with_distance():
    s = ssi_sites.sites_near(41.3871, -83.3027)
    assert [x["id"] for x in s] == ["1965", "9999"]
    assert s[0]["name"] == "White Star Quarry"
    assert s[0]["dist_km"] < 5 and s[1]["dist_km"] > 50


def test_nearest_within_max_km():
    assert ssi_sites.nearest_site_id(41.3871, -83.3027, max_km=5.0)["id"] == "1965"


def test_nearest_none_when_all_far():
    assert ssi_sites.nearest_site_id(41.3871, -83.3027, max_km=1.0) is None


def test_empty_result(monkeypatch):
    monkeypatch.setattr(ssi_sites._Locator, "query", lambda self, req: {"result": {"elements": []}})
    assert ssi_sites.sites_near(1.0, 2.0) == []
    assert ssi_sites.nearest_site_id(1.0, 2.0) is None


class _D:
    def __init__(self, lat=None, lng=None):
        self.lat, self.lng = lat, lng


def test_site_for_dive_uses_dive_coords():
    sid, src = ssi_sites.site_for_dive(_D(41.3871, -83.3027), fallback_id="99")
    assert (sid, src) == ("1965", "locator")


def test_site_for_dive_uses_sidecar_when_no_dive_coords():
    sid, src = ssi_sites.site_for_dive(
        _D(), fallback_id="99", sidecar_coords=(41.3871, -83.3027)
    )
    assert (sid, src) == ("1965", "locator")


def test_site_for_dive_falls_back_with_no_coords():
    assert ssi_sites.site_for_dive(_D(), fallback_id="99") == ("99", "config")


def test_site_for_dive_falls_back_when_nothing_near(monkeypatch):
    monkeypatch.setattr(ssi_sites._Locator, "query", lambda self, req: {"result": {"elements": []}})
    assert ssi_sites.site_for_dive(_D(1.0, 2.0), fallback_id="99") == ("99", "config")
