"""Resolve a lat/lng to an SSI dive-site id via the public locator API.

No login. The bootstrap:

  1. GET https://www.divessi.com/en/locator/divesites  (public page)
     -> Set-Cookie: PHPSESSID=...   and   <script> var SSI_APIKEY = '...'
  2. POST https://www.divessi.com/api/locationServices.php  with the SAME session
     cookie AND  x-ssi-auth: <SSI_APIKEY>   (both required; either alone -> 401)
     request={"type":"BOUNDS_CHANGED","filter":{"targets":["DiveSites"],
              "geoBounds":{south,west,north,east},"viewportCenter":{lat,lng}}}
     -> {"result":{"elements":[{"data":{"properties":{"id":"1965","name":"...",
          "lat":"41.37","lng":"-83.31","distanceToCenter":"2.03"}}}]}}
"""

from __future__ import annotations

import json
import math
import re

LOCATOR_PAGE = "https://www.divessi.com/en/locator/divesites"
LOCATION_SERVICES = "https://www.divessi.com/api/locationServices.php"
_APIKEY_RE = re.compile(r"SSI_APIKEY\s*=\s*['\"]([A-Za-z0-9]{16,80})['\"]")


class SiteLookupError(RuntimeError):
    pass


def _haversine_km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = math.radians(b_lat - a_lat), math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class _Locator:
    def __init__(self, api_key: str | None = None):
        from curl_cffi import requests

        self._s = requests.Session(impersonate="chrome")
        self.api_key = (api_key or "").strip() or None
        if not self.api_key:
            try:
                html = self._s.get(LOCATOR_PAGE, timeout=30).text or ""
            except Exception as e:
                raise SiteLookupError(f"locator page fetch failed: {e}") from e
            m = _APIKEY_RE.search(html)
            if not m:
                raise SiteLookupError("SSI_APIKEY not found on the locator page")
            self.api_key = m.group(1)
        else:
            self._s.get(LOCATOR_PAGE, timeout=30)  # still need the session cookie

    def query(self, request_obj: dict) -> dict:
        boundary = "----ssiLocator0000"
        payload = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="request"\r\n\r\n'
            f"{json.dumps(request_obj, separators=(',', ':'))}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        r = self._s.post(
            LOCATION_SERVICES,
            data=payload,
            timeout=30,
            headers={
                "Accept": "*/*",
                "Origin": "https://www.divessi.com",
                "Referer": LOCATOR_PAGE,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "x-ssi-auth": self.api_key,
            },
        )
        if r.status_code >= 400:
            raise SiteLookupError(f"{r.status_code} from locationServices: {r.text[:200]!r}")
        try:
            return r.json()
        except Exception as e:
            raise SiteLookupError(f"non-JSON reply: {r.text[:200]!r}") from e


def sites_near(lat: float, lng: float, *, api_key: str | None = None,
               half_deg: float = 0.15) -> list[dict]:
    """`{id, name, lat, lng, dist_km}` dive sites near (lat, lng), nearest first."""
    body = _Locator(api_key).query(
        {
            "type": "BOUNDS_CHANGED",
            "filter": {
                "targets": ["DiveSites"],
                "geoBounds": {
                    "south": lat - half_deg, "north": lat + half_deg,
                    "west": lng - half_deg, "east": lng + half_deg,
                },
                "viewportCenter": {"lat": lat, "lng": lng},
            },
        }
    )
    elements = (((body or {}).get("result") or {}).get("elements")) or []
    out = []
    for el in elements:
        p = ((el or {}).get("data") or {}).get("properties") or {}
        if not p.get("id"):
            continue
        s_lat, s_lng = _f(p.get("lat")), _f(p.get("lng"))
        dist = (
            _haversine_km(lat, lng, s_lat, s_lng)
            if s_lat is not None and s_lng is not None
            else _f(p.get("distanceToCenter"))
        )
        out.append({"id": str(p["id"]), "name": p.get("name", ""),
                    "lat": s_lat, "lng": s_lng, "dist_km": dist})
    out.sort(key=lambda s: (s["dist_km"] is None, s["dist_km"] or 0.0))
    return out


def nearest_site_id(lat: float, lng: float, *, api_key: str | None = None,
                    max_km: float = 5.0) -> dict | None:
    """Closest dive site within `max_km`, or None."""
    for s in sites_near(lat, lng, api_key=api_key):
        if s["dist_km"] is None or s["dist_km"] <= max_km:
            return s
    return None


def site_for_dive(dive, *, fallback_id: str | None = None, api_key: str | None = None,
                  sidecar_coords: tuple[float, float] | None = None,
                  max_km: float = 5.0) -> tuple[str | None, str]:
    """`(site_id, source)` for a dive: the public locator using the dive's own
    coords (FIT surface fix / Garmin entryLoc), else `sidecar_coords` from the
    phone, else `fallback_id` (SSI_DIVE_SITE_ID). Prints what it chose."""
    lat, lng = getattr(dive, "lat", None), getattr(dive, "lng", None)
    src = "dive"
    if (lat is None or lng is None) and sidecar_coords:
        lat, lng, src = sidecar_coords[0], sidecar_coords[1], "sidecar"
    if lat is None or lng is None:
        return fallback_id, "config"
    try:
        hit = nearest_site_id(lat, lng, api_key=api_key, max_km=max_km)
    except SiteLookupError as e:
        print(f"  site lookup failed ({e}); using SSI_DIVE_SITE_ID")
        return fallback_id, "config"
    if hit:
        d = f"{hit['dist_km']:.1f}km" if hit["dist_km"] is not None else "?km"
        print(f"  site: {hit['name']} (id {hit['id']}, {d}) from {src} {lat:.4f},{lng:.4f}")
        return hit["id"], "locator"
    print(f"  no dive site within {max_km}km of {lat:.4f},{lng:.4f}; using SSI_DIVE_SITE_ID")
    return fallback_id, "config"
