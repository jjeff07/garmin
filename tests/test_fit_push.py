import json
from pathlib import Path

from garmin_ssi.fit_push import (
    fit_sha,
    load_env_file,
    load_ledger,
    main,
    read_coords,
    save_ledger,
)

SAMPLE = str(Path(__file__).parent / "data" / "sample_dive.fit")        # no GPS
WITH_GPS = str(Path(__file__).parent / "data" / "dive_with_gps.fit")    # lap end fix


def test_fit_sha_stable_and_short():
    a, b = fit_sha(SAMPLE), fit_sha(SAMPLE)
    assert a == b and len(a) == 16


def test_ledger_roundtrip(tmp_path):
    p = tmp_path / "state" / "pushed.json"
    assert load_ledger(str(p)) == {}
    save_ledger(str(p), {"abc": {"at": "now"}})
    assert load_ledger(str(p)) == {"abc": {"at": "now"}}


def test_read_coords_sidecar(tmp_path):
    fit = tmp_path / "dive-1.fit"
    fit.write_bytes(b"x")
    assert read_coords(str(fit)) is None
    (tmp_path / "dive-1.json").write_text(json.dumps({"lat": 41.49, "lng": -81.68}))
    assert read_coords(str(fit)) == (41.49, -81.68)


def test_load_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SSI_EMAIL", raising=False)
    p = tmp_path / ".ssienv"
    p.write_text('# creds\nexport SSI_EMAIL=me@x.com\nSSI_DIVE_SITE_ID="1965"\n\n')
    load_env_file(str(p))
    import os
    assert os.environ["SSI_EMAIL"] == "me@x.com"
    assert os.environ["SSI_DIVE_SITE_ID"] == "1965"


def _stub_locator(monkeypatch):
    import garmin_ssi.ssi_sites as ss
    monkeypatch.setattr(
        ss, "nearest_site_id",
        lambda lat, lng, **k: {"id": "1965", "name": f"stub@{lat:.3f},{lng:.3f}", "dist_km": 1.0},
    )


def test_cli_lat_lng_fills_in_when_fit_has_no_fix(capsys, monkeypatch):
    _stub_locator(monkeypatch)
    assert main([SAMPLE, "--lat", "41.3871", "--lng", "-83.3027", "--dry-run"]) == 0
    assert "stub@41.387,-83.303" in capsys.readouterr().out


def test_cli_lat_lng_ignored_when_fit_has_a_fix(capsys, monkeypatch):
    _stub_locator(monkeypatch)
    assert main([WITH_GPS, "--lat", "1.0", "--lng", "2.0", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "ignoring --lat/--lng" in out
    assert "stub@41.37" in out  # used the FIT's WSQ fix, not 1,2


def test_cli_force_coords_overrides_fit_fix(capsys, monkeypatch):
    _stub_locator(monkeypatch)
    assert main([WITH_GPS, "--lat", "1.0", "--lng", "2.0", "--force-coords", "--dry-run"]) == 0
    assert "stub@1.000,2.000" in capsys.readouterr().out


def test_dry_run_maps_without_auth(capsys):
    rc = main([SAMPLE, "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "start=2026-06-06T17:10:50" in out
    assert "depth=3.8m" in out


def test_ledger_skips_already_pushed(tmp_path, capsys):
    ledger = tmp_path / "l.json"
    ledger.write_text(json.dumps({fit_sha(SAMPLE): {"at": "2026-01-01T00:00:00Z"}}))
    rc = main([SAMPLE, "--ledger", str(ledger)])  # no --dry-run, but skipped before auth
    assert rc == 0
    assert "already pushed" in capsys.readouterr().out
