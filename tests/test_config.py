import pytest

from dive_qr.config import Config


def _cfg(**kw):
    base = dict(
        garmin_tokens=None,
        garmin_email=None,
        garmin_password=None,
        garmin_cookie=None,
        garmin_csrf=None,
        garmin_app_ver=None,
        identity=None,
        output_path="x.json",
        use_fit=True,
        token_out=None,
        ssi_email=None,
        ssi_password=None,
        ssi_cookie=None,
        ssi_dive_site_id=None,
        ssi_divetype_id="24",
        ssi_comment="Imported from Garmin Descent",
        push_enabled=True,
    )
    base.update(kw)
    return Config(**base)


def test_source_name_prefers_tokens():
    assert _cfg(garmin_tokens="{}", garmin_email="a@b.c").source_name == "garminconnect"


def test_source_name_login_when_no_tokens():
    assert _cfg(garmin_email="a@b.c", garmin_password="pw").source_name == "garminconnect-login"


def test_source_name_cookie_last():
    assert _cfg(garmin_cookie="k=v").source_name == "cookie"


def test_make_source_errors_with_no_auth():
    with pytest.raises(SystemExit):
        _cfg().make_source()


def test_ssi_auth_configured():
    assert _cfg().ssi_auth_configured is False
    assert _cfg(ssi_cookie="PHPSESSID=x").ssi_auth_configured is True
    assert _cfg(ssi_email="a@b.c").ssi_auth_configured is False  # needs both
    assert _cfg(ssi_email="a@b.c", ssi_password="pw").ssi_auth_configured is True


def test_env_roundtrip(monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", " a@b.c ")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    monkeypatch.setenv("SSI_USER_ID", "123")
    for k in ("GARMIN_TOKENS", "GARMIN_COOKIE"):
        monkeypatch.delenv(k, raising=False)
    c = Config.from_env()
    assert c.garmin_email == "a@b.c"  # trimmed
    assert c.identity.user_master_id == "123"
    assert c.source_name == "garminconnect-login"
