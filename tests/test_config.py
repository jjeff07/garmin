from garmin_ssi.config import Config


def _cfg(**kw):
    base = dict(
        identity=None,
        ssi_email=None,
        ssi_password=None,
        ssi_cookie=None,
        ssi_dive_site_id=None,
        ssi_api_key=None,
        ssi_divetype_id="24",
        ssi_comment="Imported from Garmin Descent",
    )
    base.update(kw)
    return Config(**base)


def test_ssi_auth_configured():
    assert _cfg().ssi_auth_configured is False
    assert _cfg(ssi_cookie="PHPSESSID=x").ssi_auth_configured is True
    assert _cfg(ssi_email="a@b.c").ssi_auth_configured is False  # needs both
    assert _cfg(ssi_email="a@b.c", ssi_password="pw").ssi_auth_configured is True


def test_from_env_reads_and_trims(monkeypatch):
    for k in list(("SSI_EMAIL", "SSI_PASSWORD", "SSI_COOKIE", "SSI_DIVE_SITE_ID",
                   "SSI_DIVETYPE_ID", "SSI_COMMENT")):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SSI_EMAIL", "  me@x.com ")
    monkeypatch.setenv("SSI_USER_ID", "4195537")
    monkeypatch.setenv("SSI_DIVE_SITE_ID", "1965")
    c = Config.from_env()
    assert c.ssi_email == "me@x.com"
    assert c.identity.user_master_id == "4195537"
    assert c.ssi_dive_site_id == "1965"
    assert c.ssi_divetype_id == "24"  # default
    assert c.ssi_comment == "Imported from Garmin Descent"  # default
