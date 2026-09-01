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

SAMPLE = str(Path(__file__).parent / "data" / "sample_dive.fit")


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


def test_cli_lat_lng_override(capsys, monkeypatch):
    import garmin_ssi.ssi_sites as ss
    monkeypatch.setattr(
        ss, "nearest_site_id",
        lambda lat, lng, **k: {"id": "1965", "name": "White Star Quarry", "dist_km": 2.0},
    )
    rc = main([SAMPLE, "--lat", "41.3871", "--lng", "-83.3027", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "White Star Quarry" in out and "41.3871,-83.3027" in out


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
