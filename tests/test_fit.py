from pathlib import Path

import pytest

from garmin_ssi.fit import parse_fit_file
from garmin_ssi.ssi import Identity, build_ssi

SAMPLE = Path(__file__).parent / "data" / "sample_dive.fit"
WITH_GPS = Path(__file__).parent / "data" / "dive_with_gps.fit"


def test_parses_sample_dive():
    d = parse_fit_file(SAMPLE)
    # local start = 2026-06-06 21:10:50 UTC + (-04:00)
    assert d.start_local.strftime("%Y%m%d%H%M") == "202606061710"
    assert round(d.max_depth_m, 3) == 3.847
    assert round(d.divetime_s) == 1414
    assert d.water_temp_c == 27
    assert d.dive_number == 5
    assert d.water_type == "fresh"


def test_sample_dive_has_no_position():
    assert parse_fit_file(SAMPLE).lat is None


def test_surface_position_from_lap_end():
    d = parse_fit_file(WITH_GPS)
    # lap.end_position_lat/long semicircles -> White Star Quarry (~41.37, -83.31)
    assert d.lat == pytest.approx(41.3705, abs=0.01)
    assert d.lng == pytest.approx(-83.3122, abs=0.01)


def test_sample_dive_to_ssi():
    d = parse_fit_file(SAMPLE)
    ident = Identity(user_master_id="REPLACE", first_name="First", last_name="Last")
    s = build_ssi(d, ident)
    assert s == (
        "dive;noid;dive_type:0;datetime:202606061710;divetime:24;depth_m:3.8;"
        "user_master_id:REPLACE;user_firstname:First;user_lastname:Last;watertemp_c:27"
    )
