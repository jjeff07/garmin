"""Tiny HTTP session used by the SSI code, so it runs where curl_cffi can't
(iOS / a-Shell: pip has no libcurl binary). divessi.com does not need browser
fingerprint impersonation - plain urllib is enough.

`Session` is curl_cffi's when that's importable (dev / GitHub Actions, and keeps
the Garmin path's Cloudflare bypass), else a stdlib-urllib shim exposing the
same small surface: `.headers`, `.cookies` (`.keys()` / `.get()`), `.get()`,
`.post(data=dict|bytes|str)`, and a Response with `.status_code` / `.text` /
`.json()` / `.raise_for_status()`.
"""

from __future__ import annotations

import http.cookiejar
import json as _json
import urllib.error
import urllib.parse
import urllib.request

_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

try:  # pragma: no cover - exercised by env, not tests
    from curl_cffi import requests as _curl

    def Session():  # noqa: N802 - factory, mirrors class use
        return _curl.Session(impersonate="chrome")

    HTTP_BACKEND = "curl_cffi"
except Exception:  # noqa: BLE001
    _curl = None
    HTTP_BACKEND = "urllib"


class _Resp:
    def __init__(self, status_code: int, body: bytes, url: str):
        self.status_code = status_code
        self.content = body
        self.text = body.decode("utf-8", "replace")
        self.url = url

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise urllib.error.HTTPError(self.url, self.status_code, self.text[:200], None, None)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # don't follow; return the 3xx response as-is


class _Cookies:
    def __init__(self, jar: http.cookiejar.CookieJar):
        self.jar = jar

    def keys(self):
        return [c.name for c in self.jar]

    def get(self, name, default=None):
        for c in self.jar:
            if c.name == name:
                return c.value
        return default


class _UrllibSession:
    def __init__(self):
        self.headers: dict[str, str] = {"User-Agent": _UA, "Accept": "*/*"}
        self._jar = http.cookiejar.CookieJar()
        self.cookies = _Cookies(self._jar)
        self._follow = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._noredir = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar), _NoRedirect
        )

    def _do(self, method, url, *, data=None, headers=None, timeout=30, allow_redirects=True):
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data).encode()
        elif isinstance(data, str):
            data = data.encode()
        req = urllib.request.Request(url, data=data, method=method)
        merged = {**self.headers, **(headers or {})}
        for k, v in merged.items():
            if v is not None:
                req.add_header(k, v)
        opener = self._follow if allow_redirects else self._noredir
        try:
            with opener.open(req, timeout=timeout) as r:
                return _Resp(r.status, r.read(), r.geturl())
        except urllib.error.HTTPError as e:  # 4xx/5xx still carry a body
            return _Resp(e.code, e.read() if e.fp else b"", url)

    def get(self, url, *, headers=None, timeout=30, allow_redirects=True, **_):
        return self._do("GET", url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)

    def post(self, url, *, data=None, headers=None, timeout=30, allow_redirects=True, **_):
        return self._do(
            "POST", url, data=data, headers=headers, timeout=timeout, allow_redirects=allow_redirects
        )


if _curl is None:
    def Session():  # noqa: F811 - urllib fallback
        return _UrllibSession()
