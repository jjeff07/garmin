"""Configuration from environment (GitHub Actions secrets / local shell)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .ssi import Identity


@dataclass
class Config:
    # --- Garmin auth. Priority: token blob -> email+password -> browser cookie ---
    garmin_tokens: str | None       # JSON blob from bootstrap_token.py  -> GARMIN_TOKENS
    garmin_email: str | None        # -> GARMIN_EMAIL  (only used if token missing/expired)
    garmin_password: str | None     # -> GARMIN_PASSWORD
    garmin_cookie: str | None       # `Cookie:` header from a logged-in request -> GARMIN_COOKIE
    garmin_csrf: str | None         # `connect-csrf-token` header (cookie mode only)
    garmin_app_ver: str | None      # `x-app-ver` header (cookie mode only)

    identity: Identity              # SSI values (user_master_id, name) for QR + logbook push
    output_path: str                # where refresh.py writes latest.json
    use_fit: bool                   # download+parse the FIT for water temperature
    token_out: str | None           # if set, write the refreshed token blob here when it changes

    # --- MySSI logbook push (direct POST, no watch/QR) ---
    ssi_email: str | None           # -> SSI_EMAIL     } preferred: log in fresh each run,
    ssi_password: str | None        # -> SSI_PASSWORD  } nothing to expire
    ssi_cookie: str | None          # -> SSI_COOKIE    (override: whole `Cookie:` header)
    ssi_dive_site_id: str | None    # fallback SSI dive-site id -> SSI_DIVE_SITE_ID (used when no coords / no site found)
    ssi_api_key: str | None         # -> SSI_API_KEY  (optional; the locator self-fetches one otherwise)
    ssi_divetype_id: str            # 23 Education / 24 Fun Dive / 138 Scientific / 139 Work
    ssi_comment: str                # note added to each imported dive
    push_enabled: bool              # PUSH_TO_SSI=0 to disable the logbook push

    @property
    def ssi_auth_configured(self) -> bool:
        return bool((self.ssi_email and self.ssi_password) or self.ssi_cookie)

    def make_ssi_client(self):
        from .ssi_push import SSIClient

        return SSIClient(
            email=self.ssi_email, password=self.ssi_password, cookie=self.ssi_cookie
        )

    def make_source(self):
        from .garmin import CookieSource, GarminConnectSource

        if self.garmin_tokens:
            return GarminConnectSource.from_tokens(
                self.garmin_tokens,
                fallback_login=(self.garmin_email, self.garmin_password),
            )
        if self.garmin_email and self.garmin_password:
            return GarminConnectSource.from_login(self.garmin_email, self.garmin_password)
        if self.garmin_cookie:
            return CookieSource(self.garmin_cookie, self.garmin_csrf, self.garmin_app_ver)
        raise SystemExit(
            "No Garmin auth. Set GARMIN_TOKENS (run bootstrap_token.py), or "
            "GARMIN_EMAIL + GARMIN_PASSWORD, or GARMIN_COOKIE (see README.md)."
        )

    @property
    def source_name(self) -> str:
        if self.garmin_tokens:
            return "garminconnect"
        if self.garmin_email:
            return "garminconnect-login"
        return "cookie"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            garmin_tokens=_env("GARMIN_TOKENS"),
            garmin_email=_env("GARMIN_EMAIL"),
            garmin_password=_env("GARMIN_PASSWORD"),
            garmin_cookie=_env("GARMIN_COOKIE"),
            garmin_csrf=_env("GARMIN_CSRF"),
            garmin_app_ver=_env("GARMIN_APP_VER"),
            identity=Identity(
                user_master_id=_env("SSI_USER_ID"),
                first_name=_env("SSI_FIRST_NAME"),
                last_name=_env("SSI_LAST_NAME"),
                leader_id=_env("SSI_LEADER_ID"),
            ),
            output_path=os.environ.get("OUTPUT_PATH", "public/latest.json"),
            use_fit=os.environ.get("USE_FIT", "1") not in ("0", "false", "no"),
            token_out=_env("TOKEN_OUT"),
            ssi_email=_env("SSI_EMAIL"),
            ssi_password=_env("SSI_PASSWORD"),
            ssi_cookie=_env("SSI_COOKIE"),
            ssi_dive_site_id=_env("SSI_DIVE_SITE_ID"),
            ssi_api_key=_env("SSI_API_KEY"),
            ssi_divetype_id=_env("SSI_DIVETYPE_ID") or "24",
            ssi_comment=_env("SSI_COMMENT") or "Imported from Garmin Descent",
            push_enabled=os.environ.get("PUSH_TO_SSI", "1") not in ("0", "false", "no"),
        )


def _env(name: str) -> str | None:
    return (os.environ.get(name) or "").strip() or None
