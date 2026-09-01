"""Fetch dives from Garmin Connect's (undocumented) web API.

Two interchangeable backends:

  * ``GarminConnectSource``  - uses the community ``garminconnect`` package, which
    implements Garmin's mobile SSO itself (curl_cffi TLS impersonation, multi
    strategy, proactive DI-token refresh). Primary. Auth = a token blob from
    ``bootstrap_token.py``.
  * ``CookieSource``  - replays a browser ``Cookie`` header via curl_cffi. Zero
    login flow, but the cookie expires in ~3 months. Fallback.

Both expose the same tiny surface (``list_dive_summaries`` / ``download_fit``);
``build_latest_dive`` normalises whatever they return into a :class:`Dive`.

This is scraping an unsupported private API. It breaks when Garmin changes their
web app. Fine for a personal tool; do not build anything load-bearing on it.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol

DIVE_SUMMARY_PATH = "/gcsalt-api/diving/v1/dive/summary"


class GarminError(RuntimeError):
    pass


class DiveSource(Protocol):
    def list_dive_summaries(self) -> list[dict]: ...
    def download_fit(self, activity_id: int) -> bytes: ...


# --------------------------------------------------------------------------- #
# backend 1: garminconnect package
# --------------------------------------------------------------------------- #
class GarminConnectSource:
    def __init__(self, garmin, *, original_blob: str | None = None):
        self._g = garmin
        self._original_blob = (original_blob or "").strip() or None

    @property
    def token_blob(self) -> str | None:
        """Current serialized session (tokens may have been refreshed during login)."""
        try:
            return self._g.client.dumps()
        except Exception:
            return None

    @property
    def token_changed(self) -> bool:
        blob = self.token_blob
        return bool(blob) and blob != self._original_blob

    @classmethod
    def from_tokens(
        cls, token_blob: str, *, fallback_login: tuple[str | None, str | None] = (None, None)
    ) -> "GarminConnectSource":
        """Resume from a bootstrap token blob. login() refreshes the DI token
        proactively if it is near expiry, so no SSO hit in the common case.
        If the blob is unusable and email/password are supplied, fall back to a
        full login rather than failing the run."""
        from garminconnect import Garmin

        g = Garmin()
        try:
            g.login(token_blob)
            return cls(g, original_blob=token_blob)
        except Exception as e:
            email, password = fallback_login
            if not (email and password):
                raise
            print(f"  (token auth failed: {e}; falling back to email/password login)")
            return cls.from_login(email, password)

    @classmethod
    def from_login(cls, email: str, password: str) -> "GarminConnectSource":
        """Full SSO login with credentials. No MFA prompt: if Garmin demands MFA
        the run fails with a clear message instead of blocking on stdin."""
        from garminconnect import Garmin

        g = Garmin(email, password, return_on_mfa=True)
        result, _ = g.login()
        if result == "needs_mfa":
            raise GarminError(
                "Garmin is requiring an MFA code for this login. Credential-only "
                "auth can't satisfy that from CI - use GARMIN_TOKENS "
                "(run proxy/bootstrap_token.py) instead."
            )
        return cls(g)

    def list_dive_summaries(self) -> list[dict]:
        body = self._g.connectapi(DIVE_SUMMARY_PATH)
        return _extract_dives(body)

    def download_fit(self, activity_id: int) -> bytes:
        from garminconnect import Garmin

        return self._g.download_activity(
            str(activity_id), dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL
        )


# --------------------------------------------------------------------------- #
# backend 2: raw browser cookie
# --------------------------------------------------------------------------- #
class CookieSource:
    BASE = "https://connect.garmin.com"

    def __init__(self, cookie: str, csrf: str | None = None, app_ver: str | None = None):
        from curl_cffi import requests

        self._s = requests.Session(impersonate="chrome")
        headers = {
            "Cookie": cookie,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.BASE}/modern/",
            "X-Requested-With": "XMLHttpRequest",
        }
        if csrf:
            headers["connect-csrf-token"] = csrf
        if app_ver:
            headers["x-app-ver"] = app_ver
        self._s.headers.update(headers)

    def _get(self, path: str):
        r = self._s.get(self.BASE + path, timeout=30)
        if r.status_code in (401, 403):
            raise GarminError(
                f"{r.status_code} for {path} - the GARMIN_COOKIE has expired. "
                f"Copy a fresh one (proxy/README.md)."
            )
        if r.status_code >= 400:
            raise GarminError(f"{r.status_code} for {path}: {r.text[:300]}")
        return r

    def list_dive_summaries(self) -> list[dict]:
        return _extract_dives(self._get(DIVE_SUMMARY_PATH).json())

    def download_fit(self, activity_id: int) -> bytes:
        return self._get(f"/download-service/files/activity/{activity_id}").content


# --------------------------------------------------------------------------- #
# normalisation
# --------------------------------------------------------------------------- #
def _extract_dives(body) -> list[dict]:
    if isinstance(body, dict):
        dives = body.get("diveActivities", [])
    elif isinstance(body, list):
        dives = body
    else:
        dives = []
    dives.sort(key=lambda d: d.get("startTime", ""), reverse=True)
    return dives


def build_latest_dive(src: DiveSource, *, use_fit: bool = True):
    summaries = src.list_dive_summaries()
    if not summaries:
        raise GarminError("no dives in the Garmin dive logbook")
    return dive_from_summary(summaries[0], src, use_fit=use_fit)


def dive_from_summary(s: dict, src: DiveSource | None, *, use_fit: bool = True):
    from .model import Dive

    act_id = s.get("connectActivityId") or s.get("activityId")
    dive = Dive(
        start_local=_parse_iso_local(s["startTime"]),
        divetime_s=float(s.get("totalTime") or s.get("bottomTime") or 0.0),
        max_depth_m=float(s["maxDepth"]),
        activity_id=int(act_id) if act_id else None,
        avg_depth_m=_opt_float(s.get("avgDepth")),
        surface_interval_s=_opt_int(s.get("surfaceInterval")),
        dive_number=_opt_int(s.get("number")),
        name=s.get("name"),
    )
    # dive-summary JSON carries no water temperature; the FIT does.
    if use_fit and src is not None and act_id:
        try:
            from .fit import parse_fit_bytes

            fit_dive = parse_fit_bytes(src.download_fit(int(act_id)))
            dive.water_temp_c = fit_dive.water_temp_c
            dive.water_type = fit_dive.water_type
            if not dive.divetime_s:
                dive.divetime_s = fit_dive.divetime_s
        except Exception as e:  # enrichment only; never fatal
            print(f"  (FIT enrich skipped: {e})")
    return dive


def _parse_iso_local(value: str) -> dt.datetime:
    """'2026-06-06T17:10:50-04:00' -> naive local wall time (17:10:50)."""
    d = dt.datetime.fromisoformat(value)
    return d.replace(tzinfo=None) if d.tzinfo else d


def _opt_float(v):
    return None if v is None else float(v)


def _opt_int(v):
    return None if v is None else int(v)
