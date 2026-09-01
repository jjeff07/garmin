from garmin_ssi.refresh import persist_token


class FakeSource:
    def __init__(self, changed, blob="{\"oauth1\": \"new\"}"):
        self.token_changed = changed
        self.token_blob = blob


def test_no_write_when_token_unchanged(tmp_path):
    out = tmp_path / "tok.new"
    assert persist_token(FakeSource(changed=False), str(out)) is False
    assert not out.exists()


def test_no_write_when_token_out_unset():
    assert persist_token(FakeSource(changed=True), None) is False


def test_writes_blob_without_trailing_newline(tmp_path):
    out = tmp_path / "tok.new"
    assert persist_token(FakeSource(changed=True, blob='{"a":1}'), str(out)) is True
    assert out.read_text() == '{"a":1}'  # exact, no newline


def test_ignores_source_without_token_attrs(tmp_path):
    out = tmp_path / "tok.new"
    assert persist_token(object(), str(out)) is False
    assert not out.exists()
