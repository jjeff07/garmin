"""Configuration from the environment (a Shortcut env-file / shell / CI secrets)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .ssi import Identity


@dataclass
class Config:
    identity: Identity              # SSI_USER_ID / name -> odin_user_log_* fields

    # --- MySSI auth: email+password (preferred; fresh login each run) or a cookie ---
    ssi_email: str | None           # -> SSI_EMAIL
    ssi_password: str | None        # -> SSI_PASSWORD
    ssi_cookie: str | None          # -> SSI_COOKIE  (whole `Cookie:` header, alternative)

    ssi_dive_site_id: str | None    # -> SSI_DIVE_SITE_ID  (fallback when coords find no public site)
    ssi_api_key: str | None         # -> SSI_API_KEY  (optional; the locator self-fetches one)
    ssi_divetype_id: str            # 23 Education / 24 Fun Dive / 138 Scientific / 139 Work
    ssi_comment: str                # note added to each imported dive

    @property
    def ssi_auth_configured(self) -> bool:
        return bool((self.ssi_email and self.ssi_password) or self.ssi_cookie)

    def make_ssi_client(self):
        from .ssi_push import SSIClient

        return SSIClient(
            email=self.ssi_email, password=self.ssi_password, cookie=self.ssi_cookie
        )

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            identity=Identity(
                user_master_id=_env("SSI_USER_ID"),
                first_name=_env("SSI_FIRST_NAME"),
                last_name=_env("SSI_LAST_NAME"),
                leader_id=_env("SSI_LEADER_ID"),
            ),
            ssi_email=_env("SSI_EMAIL"),
            ssi_password=_env("SSI_PASSWORD"),
            ssi_cookie=_env("SSI_COOKIE"),
            ssi_dive_site_id=_env("SSI_DIVE_SITE_ID"),
            ssi_api_key=_env("SSI_API_KEY"),
            ssi_divetype_id=_env("SSI_DIVETYPE_ID") or "24",
            ssi_comment=_env("SSI_COMMENT") or "Imported from Garmin Descent",
        )


def _env(name: str) -> str | None:
    return (os.environ.get(name) or "").strip() or None
