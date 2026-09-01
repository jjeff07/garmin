"""Build the MySSI dive-import QR payload.

Format (reverse-engineered; plain text scanned by the MySSI mobile app):

    dive;noid;<key>:<value>;<key>:<value>;...

Fields may be omitted. MySSI shows an editable review screen after the scan,
so anything not encoded here (dive site, buddy, free-text notes) is filled in
there. `site` deliberately is NOT encoded: it needs SSI's internal dive-site
database id, which cannot be derived from Garmin data.

References:
  - https://groups.google.com/g/subsurface-divelog/c/VFrNahh8UAc
  - https://www.divessi.com/en/blog/environment/page/expansion-universal-qr-code-scanner-6764.html
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Dive

PREFIX = "dive;noid;"


@dataclass
class Identity:
    """Static per-diver values. Pull `user_master_id` from your MySSI profile
    (or from a QR the MySSI app itself generated for you)."""

    user_master_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    leader_id: str | None = None  # instructor / dive leader SSI id, if you always log one


def _fmt_depth(m: float) -> str:
    return f"{m:.1f}"


def build_ssi(dive: Dive, identity: Identity | None = None, *, dive_type: int = 0) -> str:
    """Return the full `dive;noid;...` string for `dive`.

    `dive_type` 0 = recreational/open-circuit single gas (matches Garmin SINGLE_GAS).
    """
    identity = identity or Identity()
    parts: list[str] = [f"dive_type:{dive_type}"]

    parts.append("datetime:" + dive.start_local.strftime("%Y%m%d%H%M"))
    parts.append("divetime:" + str(round(dive.divetime_s / 60)))
    parts.append("depth_m:" + _fmt_depth(dive.max_depth_m))

    if identity.user_master_id:
        parts.append("user_master_id:" + identity.user_master_id)
    if identity.first_name:
        parts.append("user_firstname:" + identity.first_name)
    if identity.last_name:
        parts.append("user_lastname:" + identity.last_name)
    if identity.leader_id:
        parts.append("user_leader_id:" + identity.leader_id)

    if dive.water_temp_c is not None:
        parts.append("watertemp_c:" + str(round(dive.water_temp_c)))
    if dive.air_temp_c is not None:
        parts.append("airtemp_c:" + str(round(dive.air_temp_c)))

    return PREFIX + ";".join(parts)
