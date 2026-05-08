import json

import pytest

from loom.runtimes.hiagent.api_client import HiagentAPIClient, HiagentAPIError


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _HTTP:
    def __init__(self, responses: list[_Response]):
        self.responses = responses
        self.calls: list[dict] = []

    def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> _Response:
        self.calls.append({"url": url, "content": content, "headers": headers})
        return self.responses.pop(0)


def _client(http: _HTTP | None = None) -> HiagentAPIClient:
    return HiagentAPIClient(
        base_url="http://example.test",
        ak="HIA_TEST",
        sk="secret",
        workspace_id="ws_1",
        http_client=http,
    )


def test_base_url_defaults_to_top_gateway_port():
    c = _client()
    assert c.base_url == "http://example.test:30040"


def test_sign_generates_authorization_header():
    c = _client()
    body = b'{"WorkspaceID":"ws_1"}'
    headers = c._sign("POST", "/", {"Action": "CheckAppByName", "Version": "2023-08-01"}, body)
    assert headers["Authorization"].startswith("HMAC-SHA256 Credential=HIA_TEST/")
    assert "SignedHeaders=content-type;host;x-content-sha256;x-date" in headers["Authorization"]
    assert headers["X-Content-Sha256"]
    assert headers["X-Date"]
    assert headers["Host"] == "example.test:30040"


def test_post_includes_signed_headers():
    http = _HTTP([_Response({"Result": {"ok": True}})])
    c = _client(http)
    result = c._post("CheckAppByName", {"WorkspaceID": "ws_1", "Name": "demo"})
    assert result == {"ok": True}
    call = http.calls[0]
    assert call["url"].startswith("http://example.test:30040/?Action=CheckAppByName")
    assert call["headers"]["Authorization"].startswith("HMAC-SHA256 Credential=HIA_TEST/")
    assert json.loads(call["content"]) == {"WorkspaceID": "ws_1", "Name": "demo"}


def test_check_app_by_name_returns_bool():
    http = _HTTP([_Response({"Result": {"Reduplicated": True}})])
    assert _client(http).check_app_by_name("demo") is True


def test_create_app_returns_app_id():
    http = _HTTP([_Response({"Result": {"AppID": "app_123"}})])
    app_id = _client(http).create_app(name="demo", app_type="Chat", description="desc")
    assert app_id == "app_123"


def test_list_workspace_models_uses_aigw_service():
    http = _HTTP([
        _Response(
            {
                "Result": {
                    "Items": [
                        {
                            "ID": "model_1",
                            "Name": "Default Model",
                            "Type": "text-generation",
                            "IsDefault": True,
                        }
                    ],
                    "Total": 1,
                }
            }
        )
    ])
    models = _client(http).list_workspace_models()
    assert models[0]["ID"] == "model_1"
    auth = http.calls[0]["headers"]["Authorization"]
    assert "/cn-north-1/aigw/request" in auth
    assert "Action=ListModelByWorkspaceGrant" in http.calls[0]["url"]


def test_resolve_default_text_generation_model_prefers_default():
    http = _HTTP([
        _Response(
            {
                "Result": {
                    "Items": [
                        {"ID": "model_new", "Type": "text-generation", "IsDefault": False},
                        {"ID": "model_default", "Type": "text-generation", "IsDefault": True},
                    ],
                    "Total": 2,
                }
            }
        )
    ])
    assert _client(http).resolve_default_text_generation_model_id() == "model_default"


def test_response_metadata_error_raises():
    http = _HTTP([
        _Response({"ResponseMetadata": {"Error": {"Code": 401, "Message": "Not logged in"}}})
    ])
    with pytest.raises(HiagentAPIError, match="Not logged in"):
        _client(http).check_app_by_name("demo")


def test_http_error_includes_response_body():
    http = _HTTP([_Response({"message": "bad publish payload"}, status_code=400)])
    with pytest.raises(HiagentAPIError, match="bad publish payload"):
        _client(http).check_app_by_name("demo")
