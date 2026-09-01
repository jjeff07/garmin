from datetime import datetime

from dive_qr.model import Dive
from dive_qr.ssi import Identity, build_ssi


def _dive(**kw):
    base = dict(
        start_local=datetime(2026, 6, 6, 17, 10, 50),
        divetime_s=1414.323,
        max_depth_m=3.847,
        water_temp_c=27.0,
    )
    base.update(kw)
    return Dive(**base)


def test_minimal_payload_no_identity():
    s = build_ssi(_dive(water_temp_c=None))
    assert s == "dive;noid;dive_type:0;datetime:202606061710;divetime:24;depth_m:3.8"


def test_full_payload_with_identity_and_temp():
    ident = Identity(user_master_id="1722281", first_name="Joe", last_name="Diver")
    s = build_ssi(_dive(), ident)
    assert s == (
        "dive;noid;dive_type:0;datetime:202606061710;divetime:24;depth_m:3.8;"
        "user_master_id:1722281;user_firstname:Joe;user_lastname:Diver;watertemp_c:27"
    )


def test_depth_always_one_decimal():
    assert "depth_m:18.0;" in build_ssi(_dive(max_depth_m=18.0)) + ";"
    assert "depth_m:12.8" in build_ssi(_dive(max_depth_m=12.83))


def test_divetime_rounds_to_nearest_minute():
    assert "divetime:24;" in build_ssi(_dive(divetime_s=1414.323)) + ";"
    assert "divetime:23;" in build_ssi(_dive(divetime_s=1380.0)) + ";"
    assert "divetime:20;" in build_ssi(_dive(divetime_s=1200.0)) + ";"


def test_air_temp_and_leader_optional():
    ident = Identity(user_master_id="1", first_name="A", last_name="B", leader_id="999")
    s = build_ssi(_dive(air_temp_c=31.4), ident)
    assert "user_leader_id:999;" in s + ";"
    assert "airtemp_c:31" in s


def test_payload_is_scannable_size():
    ident = Identity(user_master_id="1722281", first_name="Joe", last_name="Diver")
    # comfortably inside QR byte-mode capacity for a low version at ECC M
    assert len(build_ssi(_dive(), ident)) < 160
