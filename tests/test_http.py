from garmin_ssi import _http


def test_backend_is_known():
    assert _http.HTTP_BACKEND in ("curl_cffi", "urllib")


def test_session_factory_has_the_surface_we_use():
    s = _http.Session()
    assert hasattr(s, "get") and hasattr(s, "post")
    assert hasattr(s, "headers")
    assert hasattr(s, "cookies")


def test_urllib_session_interface():
    s = _http._UrllibSession()
    assert s.headers["User-Agent"]
    assert s.cookies.keys() == []
    assert s.cookies.get("PHPSESSID") is None
    # encodes a dict body as urlencoded (no network)
    assert callable(s.get) and callable(s.post)


def test_urllib_resp_json_and_status():
    r = _http._Resp(200, b'{"a": 1}', "http://x")
    assert r.status_code == 200 and r.json() == {"a": 1}
    bad = _http._Resp(404, b"nope", "http://x")
    assert bad.status_code == 404
