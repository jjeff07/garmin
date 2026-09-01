from datetime import datetime
from pathlib import Path

from dive_qr.fit import parse_fit_file
from dive_qr.model import Dive
from dive_qr.ssi import Identity
from dive_qr.ssi_push import DIVETYPE_FUN_DIVE, dive_to_form

SAMPLE = Path(__file__).parent / "data" / "sample_dive.fit"
IDENT = Identity(user_master_id="4195537", first_name="Justin", last_name="Jeffery")


def test_sample_dive_maps_to_form():
    b = dive_to_form(parse_fit_file(SAMPLE), IDENT)
    assert b["odin_user_log_user_master_id"] == "4195537"
    assert b["source"] == "mydl_18_add_AddDiveOnline"
    assert b["odin_user_log_dive_type"] == "0"
    assert (b["date_sel2_dd"], b["date_sel2_mm"], b["date_sel2_yy"]) == ("06", "06", "2026")
    assert b["odin_user_log_entry_time"] == "17:10"
    assert b["odin_user_log_dive_nr"] == "5"
    assert b["odin_user_log_var_divetype_id"] == DIVETYPE_FUN_DIVE
    assert b["odin_user_log_divetime"] == "24"
    assert b["odin_user_log_depth_m"] == "3.8"
    assert b["odin_user_log_depth_ft"] == "12.6"
    assert b["odin_user_log_watertemp_c"] == "27"
    assert b["odin_user_log_watertemp_f"] == "81"
    assert b["odin_user_log_var_watertype_id"] == "4"  # FIT water_type "fresh"
    assert b["dive_site_bow"] == "fresh"
    assert b["submit"] == "Submit"


def test_form_has_full_field_set():
    b = dive_to_form(parse_fit_file(SAMPLE), IDENT)
    assert len(b) == 82  # complete add-form body


def test_optional_fields_blank_when_absent():
    d = Dive(start_local=datetime(2026, 1, 2, 8, 5), divetime_s=1800, max_depth_m=18.0)
    b = dive_to_form(d, IDENT)
    assert b["odin_user_log_watertemp_c"] == ""
    assert b["odin_user_log_var_watertype_id"] == ""
    assert b["odin_user_log_dive_sites_id"] == ""
    assert b["odin_user_log_dive_nr"] == ""
    assert b["odin_user_log_depth_m"] == "18.0"


def test_dive_site_id_and_comment_applied():
    d = Dive(start_local=datetime(2026, 1, 2, 8, 5), divetime_s=1800, max_depth_m=18.0)
    b = dive_to_form(d, IDENT, dive_site_id="222708", comment="hi")
    assert b["odin_user_log_dive_sites_id"] == "222708"
    assert b["odin_user_log_comment"] == "hi"
