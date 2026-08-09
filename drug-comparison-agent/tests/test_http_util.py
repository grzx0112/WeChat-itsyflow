import json
import urllib.error
from unittest import mock

from scripts.http_util import get_json, _reset_rate_limit


class _FakeResp:
    def __init__(self, body): self._body = body
    def read(self): return self._body.encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_get_json_success():
    _reset_rate_limit()
    body = '{"ok": true}'
    with mock.patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        assert get_json("https://x/api") == {"ok": True}


def test_get_json_retries_then_succeeds():
    _reset_rate_limit()
    body = '{"ok": true}'
    side = [urllib.error.URLError("boom"), urllib.error.URLError("boom"), _FakeResp(body)]
    with mock.patch("urllib.request.urlopen", side_effect=side), \
         mock.patch("time.sleep"):
        assert get_json("https://x/api") == {"ok": True}


def test_get_json_fails_after_retries():
    _reset_rate_limit()
    with mock.patch("urllib.request.urlopen",
                    side_effect=urllib.error.URLError("boom")), \
         mock.patch("time.sleep"):
        try:
            get_json("https://x/api")
            assert False, "应抛 RuntimeError"
        except RuntimeError:
            pass


def test_get_json_appends_params():
    _reset_rate_limit()
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResp('{}')
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        get_json("https://x/api", params={"a": "b c", "n": 1})
    assert "a=b+c" in captured["url"] and "n=1" in captured["url"]
