"""Log a dive straight into the MySSI web logbook - no watch, no QR.

    POST https://my.divessi.com/code/process/mydivelog_18.php   (form-urlencoded)

Auth is the browser session cookie only (PHPSESSID [+ mid]); there is no CSRF
token. A successful create returns a ~376-byte HTML stub that redirects to
/mydivelog. Anything else (the add form re-rendered, a login page) is a failure.

Full field reference: reference/ssi_logbook_api.md
"""

from __future__ import annotations

import re

from ._http import Session
from .model import Dive, Identity

ENDPOINT = "https://my.divessi.com/code/process/mydivelog_18.php"
SIGNIN = "https://www.divessi.com/bridge/code/process/signin"
HOME = "https://www.divessi.com/en/home"


class SSIAuthError(RuntimeError):
    pass

DIVE_TYPE_SCUBA = "0"          # 2 XR, 4 SCR, 8 CCR, 6 Freediving
DIVETYPE_FUN_DIVE = "24"       # 23 Education, 138 Scientific, 139 Work
_WATERTYPE = {"fresh": "4", "salt": "5"}

# The add form posts 82 fields; most are empty but expected to be present.
# Captured 2026-09-01 from a real dive. Only structural defaults are non-empty.
_FORM_TEMPLATE: dict[str, str] = {
    "odin_user_log_user_master_id": "",
    "source": "mydl_18_add_AddDiveOnline",
    "odin_user_log_animal_ids": "",
    "odin_user_log_transferDate": "",
    "odin_user_log_diveComputer": "",
    "odin_user_log_diveComputerData_ue": "",
    "odin_user_log_si_before": "",
    "odin_user_log_gf_set": "",
    "odin_user_log_gf_set_1": "",
    "odin_user_log_gf_set_2": "",
    "odin_user_log_gf_end": "",
    "odin_user_log_cns_start": "",
    "odin_user_log_cns_end": "",
    "odin_user_log_otu_start": "",
    "odin_user_log_otu_end": "",
    "odin_user_log_alarm_deco_stop": "",
    "odin_user_log_alarm_fast_ascent": "",
    "odin_user_log_alarm_deco_violation": "",
    "odin_user_log_divecomputer_dive_ref": "",
    "odin_user_log_divecomputer_ref": "",
    "odin_user_log_divecomputer_imported": "",
    "odin_user_log_dive_type": DIVE_TYPE_SCUBA,
    "date_sel2_dd": "",
    "date_sel2_mm": "",
    "date_sel2_yy": "",
    "odin_user_log_entry_time": "",
    "odin_user_log_dive_nr": "",
    "odin_user_log_var_divetype_id": DIVETYPE_FUN_DIVE,
    "log_linked_brevet_rule_id": "0",
    "odin_user_log_leader_nr": "",
    "log_linked_facility_id": "",
    "odin_user_log_dive_sites_id": "",
    "dive_site_bow": "",
    "adr": "",
    "searchSite": "",
    "odin_user_log_divetime": "",
    "odin_user_log_depth_m": "",
    "odin_user_log_depth_ft": "",
    "odin_user_log_avg_depth_m": "",
    "odin_user_log_avg_depth_ft": "",
    "odin_user_log_weight_kg": "",
    "odin_user_log_weight_lb": "",
    "odin_user_log_gearconfiguration_id": "",
    "odin_user_log_var_tanktype_id": "",
    "odin_user_log_tank_vol_l": "",
    "odin_user_log_tank_vol_cuft": "",
    "odin_user_log_pressure_start_bar": "",
    "odin_user_log_pressure_start_psi": "",
    "odin_user_log_pressure_end_bar": "",
    "odin_user_log_pressure_end_psi": "",
    "odin_user_log_amv_l": "",
    "odin_user_log_amv_psi": "",
    "odin_user_log_deco_time": "",
    "odin_user_log_deco_gas_tanktype_id": "",
    "odin_user_log_deco_gas_tank_vol_l": "",
    "odin_user_log_deco_gas_tank_vol_cuft": "",
    "odin_user_log_deco_gas_o2": "",
    "odin_user_log_deco_gas_start_bar": "",
    "odin_user_log_deco_gas_start_psi": "",
    "odin_user_log_deco_gas_end_bar": "",
    "odin_user_log_deco_gas_end_psi": "",
    "log_extended_data_cleanup_weight_kg": "",
    "log_extended_data_cleanup_weight_lb": "",
    "odin_user_log_var_specialdive_id[]": "",
    "odin_user_log_rating": "",
    "odin_user_log_var_water_body_id": "",
    "odin_user_log_var_entry_id": "",
    "odin_user_log_var_watertype_id": "",
    "odin_user_log_var_current_id": "",
    "odin_user_log_var_surface_id": "",
    "odin_user_log_var_weather_id": "",
    "odin_user_log_airtemp_c": "",
    "odin_user_log_airtemp_f": "",
    "odin_user_log_watertemp_c": "",
    "odin_user_log_watertemp_f": "",
    "odin_user_log_watertemp_max_c": "",
    "odin_user_log_watertemp_max_f": "",
    "odin_user_log_vis_m": "",
    "odin_user_log_vis_ft": "",
    "odin_user_log_gear_details": "",
    "odin_user_log_comment": "",
    "submit": "Submit",
}


def _c_to_f(c: float) -> int:
    return round(c * 9 / 5 + 32)


def _m_to_ft(m: float) -> float:
    return round(m * 3.28084, 1)


def dive_to_form(
    dive: Dive,
    identity: Identity,
    *,
    dive_site_id: str | None = None,
    divetype_id: str = DIVETYPE_FUN_DIVE,
    comment: str = "Imported from Garmin",
) -> dict[str, str]:
    """Map a normalised :class:`Dive` onto the MySSI add-dive form body."""
    b = dict(_FORM_TEMPLATE)
    b["odin_user_log_user_master_id"] = identity.user_master_id or ""
    b["date_sel2_dd"] = dive.start_local.strftime("%d")
    b["date_sel2_mm"] = dive.start_local.strftime("%m")
    b["date_sel2_yy"] = dive.start_local.strftime("%Y")
    b["odin_user_log_entry_time"] = dive.start_local.strftime("%H:%M")
    b["odin_user_log_dive_nr"] = "" if dive.dive_number is None else str(dive.dive_number)
    b["odin_user_log_var_divetype_id"] = divetype_id
    b["odin_user_log_divetime"] = str(round(dive.divetime_s / 60))
    b["odin_user_log_depth_m"] = f"{dive.max_depth_m:.1f}"
    b["odin_user_log_depth_ft"] = f"{_m_to_ft(dive.max_depth_m):.1f}"
    if dive.avg_depth_m is not None:
        b["odin_user_log_avg_depth_m"] = f"{dive.avg_depth_m:.1f}"
        b["odin_user_log_avg_depth_ft"] = f"{_m_to_ft(dive.avg_depth_m):.1f}"
    if dive.water_temp_c is not None:
        b["odin_user_log_watertemp_c"] = str(round(dive.water_temp_c))
        b["odin_user_log_watertemp_f"] = str(_c_to_f(dive.water_temp_c))
    if dive.air_temp_c is not None:
        b["odin_user_log_airtemp_c"] = str(round(dive.air_temp_c))
        b["odin_user_log_airtemp_f"] = str(_c_to_f(dive.air_temp_c))
    wt = _WATERTYPE.get((dive.water_type or "").lower())
    if wt:
        b["odin_user_log_var_watertype_id"] = wt
        b["dive_site_bow"] = (dive.water_type or "").lower()
    if dive_site_id:
        b["odin_user_log_dive_sites_id"] = str(dive_site_id)
    b["odin_user_log_comment"] = comment
    return b


class SSIClient:
    """Authenticated MySSI session. Prefer email/password (logs in fresh, no cookie
    to expire); a raw `Cookie:` header still works as an override.

    The signin cookie is scoped to `.divessi.com`, so one session covers both the
    www. login host and the my. logbook host.
    """

    def __init__(
        self,
        *,
        email: str | None = None,
        password: str | None = None,
        cookie: str | None = None,
    ):
        self._s = Session()
        self._s.headers.update({"Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"})
        if email and password:
            self._login(email, password)
        elif cookie:
            self._s.headers["Cookie"] = cookie.strip()
        else:
            raise ValueError("SSIClient needs email+password or cookie")

    def _login(self, email: str, password: str) -> None:
        pre = self._s.get(HOME, timeout=30)  # seed a PHPSESSID
        form = {
            "username": email,
            "password": password,
            "rememberMe": "off",
            "auth": "Portal",
        }
        r = self._s.post(
            SIGNIN,
            data=form,
            timeout=30,
            allow_redirects=False,
            headers={
                "Origin": "https://www.divessi.com",
                "Referer": HOME,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        text = r.text or ""
        print(
            f"  SSI signin: pre={pre.status_code} post={r.status_code} "
            f"cookies={sorted(self._s.cookies.keys())} body[:120]={text[:120]!r}"
        )
        ok = r.status_code == 200 and ("url=/myssi" in text or '"success":true' in text)
        if not ok:
            hint = ""
            if "NOT_AUTHORIZED" in text or '"success":false' in text:
                hint = " (credentials rejected by SSI - check SSI_EMAIL / SSI_PASSWORD)"
            raise SSIAuthError(
                f"SSI login failed (status {r.status_code}){hint}. Body: {text[:200]!r}"
            )
        # The signin cookie is set for domain=.divessi.com; pin PHPSESSID/mid as an
        # explicit header so every following request (any host) carries it.
        self._pin_session_cookies()
        # Follow the browser's post-signin landing (www -> my).
        try:
            self._s.get("https://www.divessi.com/myssi", timeout=30, allow_redirects=True)
        except Exception:
            pass
        # Confirm the session is authenticated on the logbook host: the overview
        # only lists existing dives (mydivelog/show/) when logged in.
        chk = self._s.get("https://my.divessi.com/mydivelog", timeout=30, allow_redirects=True)
        cbody = chk.text or ""
        authed = "mydivelog/show/" in cbody or 'id="add_log"' in cbody or "Logbook - Overview" in cbody
        print(f"  SSI logbook check: status={chk.status_code} authed={authed} len={len(cbody)}")
        if not authed:
            raise SSIAuthError(
                "signed in at www.divessi.com but the my.divessi.com session is not "
                f"authenticated (status {chk.status_code}) - login or cookie carry-over failed"
            )

    def _pin_session_cookies(self) -> None:
        pairs = []
        try:
            for name in ("PHPSESSID", "mid"):
                val = self._s.cookies.get(name)
                if val:
                    pairs.append(f"{name}={val}")
        except Exception:
            for c in getattr(self._s.cookies, "jar", []):
                if getattr(c, "name", None) in ("PHPSESSID", "mid"):
                    pairs.append(f"{c.name}={c.value}")
        if pairs:
            self._s.headers["Cookie"] = "; ".join(pairs)

    def create_dive(self, body: dict[str, str]) -> dict:
        if not body.get("odin_user_log_dive_sites_id"):
            return {
                "ok": False, "status": None, "bytes": 0,
                "detail": "no dive site - mydivelog_18.php silently drops a dive with no "
                          "odin_user_log_dive_sites_id. Set SSI_DIVE_SITE_ID.",
            }
        before = self._dive_count()
        r = self._s.post(
            ENDPOINT,
            data=body,
            timeout=30,
            allow_redirects=False,
            headers={
                "Origin": "https://my.divessi.com",
                "Referer": "https://my.divessi.com/mydivelog/add",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        text = r.text or ""
        low = text.lower()
        redirected_ok = (
            r.status_code == 200 and "url=/mydivelog" in text and "/mydivelog/add" not in text
        )
        if not redirected_ok:
            if "login" in low or "sign in" in low or r.status_code in (301, 302, 401, 403):
                detail = "session rejected - login/cookie invalid (reference/ssi_logbook_api.md)"
            else:
                detail = f"unexpected response: {text[:280]!r}"
            return {"ok": False, "status": r.status_code, "bytes": len(text), "detail": detail}

        # The redirect stub is returned even when the POST is silently dropped, so
        # confirm a new dive actually appeared.
        after = self._dive_count()
        if before is not None and after is not None:
            if after > before:
                return {"ok": True, "status": r.status_code, "bytes": len(text),
                        "detail": f"created (logbook {before} -> {after} dives)"}
            return {"ok": False, "status": r.status_code, "bytes": len(text),
                    "detail": f"POST accepted but no new dive appeared "
                              f"({before} -> {after}) - a required field was rejected"}
        return {"ok": True, "status": r.status_code, "bytes": len(text),
                "detail": "created (redirect ok; could not read logbook to confirm)"}

    def _dive_count(self) -> int | None:
        """Number of dives in the logbook overview, or None if it can't be read."""
        try:
            html = self._s.get("https://my.divessi.com/mydivelog", timeout=30).text or ""
        except Exception:
            return None
        if "mydivelog/show/" not in html:  # not the rendered table -> can't judge
            return None
        return len(set(re.findall(r"/mydivelog/show/([0-9_]+)", html)))
