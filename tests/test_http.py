from garmin_ssi._http import Session, _Resp


def test_session_surface():
    s = Session()
    assert s.headers["User-Agent"]
    assert s.cookies.keys() == []
    assert s.cookies.get("PHPSESSID") is None
    assert callable(s.get) and callable(s.post)


def test_resp_json_and_status():
    r = _Resp(200, b'{"a": 1}', "http://x")
    assert r.status_code == 200 and r.json() == {"a": 1}
    assert _Resp(404, b"nope", "http://x").status_code == 404
