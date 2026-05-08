"""Hiagent self-hosted TOP API client.

The management API is exposed through Hiagent's TOP gateway, not the UI
`/api/proxy/api/v1/*` session-cookie path. The working self-hosted endpoint is
`http://<host>:30040/?Action=<Action>&Version=2023-08-01` with Volcengine V4
HMAC headers. For app-management actions the effective TOP service is `app`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urlparse, urlunparse

import httpx

_DEFAULT_REGION = "cn-north-1"
_DEFAULT_SERVICE = "app"
_DEFAULT_VERSION = "2023-08-01"
_DEFAULT_TOP_PORT = 30040


class HiagentAPIError(RuntimeError):
    """Raised when Hiagent TOP API returns an HTTP or ResponseMetadata error."""


@dataclass(frozen=True)
class CallDebug:
    """Non-secret signing diagnostics for auth failures."""

    canonical_request: str
    string_to_sign: str


class HiagentAPIClient:
    """Minimal synchronous Hiagent TOP client for MVP push flow."""

    def __init__(
        self,
        *,
        base_url: str,
        ak: str,
        sk: str,
        workspace_id: str,
        account_id: str | None = None,
        region: str = _DEFAULT_REGION,
        service: str = _DEFAULT_SERVICE,
        version: str = _DEFAULT_VERSION,
        http_client: httpx.Client | Any | None = None,
    ) -> None:
        self.base_url = _normalize_top_base_url(base_url)
        self.ak = ak
        self.sk = sk
        self.workspace_id = workspace_id
        self.account_id = account_id
        self.region = region
        self.service = service
        self.version = version
        self._http = http_client or httpx.Client(timeout=30.0, trust_env=False)
        self._last_debug: CallDebug | None = None

    @classmethod
    def from_env(cls) -> HiagentAPIClient:
        """Build from `.env`-loaded process environment."""
        host = os.environ.get("HIAGENT_TOP_BASE_URL") or os.environ.get("HIAGENT_HOST")
        if not host:
            host = os.environ.get("HIAGENT_BASE_URL", "")
        missing = [
            name
            for name in ["HIAGENT_AK", "HIAGENT_SK", "HIAGENT_WORKSPACE_ID"]
            if not os.environ.get(name)
        ]
        if not host:
            missing.append("HIAGENT_HOST")
        if missing:
            raise HiagentAPIError(f"missing required Hiagent env var(s): {', '.join(missing)}")
        return cls(
            base_url=host,
            ak=os.environ["HIAGENT_AK"],
            sk=os.environ["HIAGENT_SK"],
            workspace_id=os.environ["HIAGENT_WORKSPACE_ID"],
            account_id=os.environ.get("HIAGENT_ACCOUNT_ID"),
            region=os.environ.get("HIAGENT_REGION", _DEFAULT_REGION),
            service=os.environ.get("HIAGENT_SERVICE", _DEFAULT_SERVICE),
            version=os.environ.get("HIAGENT_VERSION", _DEFAULT_VERSION),
        )

    @property
    def last_debug(self) -> CallDebug | None:
        return self._last_debug

    def _sign(
        self,
        method: str,
        path: str,
        query: dict[str, str],
        body: bytes,
        *,
        service: str | None = None,
    ) -> dict[str, str]:
        signing_service = service or self.service
        parsed = urlparse(self.base_url)
        host = parsed.netloc
        x_date = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        date = x_date[:8]
        body_hash = _sha256_hex(body)
        headers = {
            "Content-Type": "application/json",
            "Host": host,
            "X-Date": x_date,
            "X-Content-Sha256": body_hash,
        }
        signed_headers = {
            key.lower(): value
            for key, value in headers.items()
            if key in {"Content-Type", "Content-Md5", "Host"} or key.startswith("X-")
        }
        if "host" in signed_headers and ":" in signed_headers["host"]:
            hostname, port = signed_headers["host"].rsplit(":", 1)
            if port in {"80", "443"}:
                signed_headers["host"] = hostname

        signed_header_names = ";".join(sorted(signed_headers))
        canonical_headers = "".join(
            f"{key}:{signed_headers[key]}\n" for key in sorted(signed_headers)
        )
        canonical_request = "\n".join(
            [
                method.upper(),
                _norm_uri(path),
                _norm_query(query),
                canonical_headers,
                signed_header_names,
                body_hash,
            ]
        )
        credential_scope = f"{date}/{self.region}/{signing_service}/request"
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                x_date,
                credential_scope,
                _sha256_hex(canonical_request.encode("utf-8")),
            ]
        )
        key = _signing_key(self.sk, date, self.region, signing_service)
        signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        headers["Authorization"] = (
            f"HMAC-SHA256 Credential={self.ak}/{credential_scope}, "
            f"SignedHeaders={signed_header_names}, Signature={signature}"
        )
        self._last_debug = CallDebug(
            canonical_request=canonical_request,
            string_to_sign=string_to_sign,
        )
        return headers

    def _post(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        service: str | None = None,
    ) -> dict[str, Any]:
        query = {"Action": action, "Version": self.version}
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        parsed = urlparse(self.base_url)
        path = parsed.path or "/"
        url = urlunparse((parsed.scheme, parsed.netloc, path, "", urlencode(query), ""))
        headers = self._sign("POST", path, query, body, service=service)
        try:
            response = self._http.post(url, content=body, headers=headers)
        except Exception as e:
            raise HiagentAPIError(f"Hiagent API {action} request failed: {e}") from e
        try:
            data = response.json()
        except Exception as e:
            if getattr(response, "status_code", 0) >= 400:
                raise HiagentAPIError(
                    f"Hiagent API {action} HTTP {response.status_code}: {response.text}"
                ) from e
            raise HiagentAPIError(f"Hiagent API {action} returned invalid JSON: {e}") from e
        if not isinstance(data, dict):
            raise HiagentAPIError(f"Hiagent API {action} returned non-object JSON")
        meta = data.get("ResponseMetadata")
        if isinstance(meta, dict) and meta.get("Error"):
            error = meta["Error"]
            if isinstance(error, dict):
                code = error.get("Code", "unknown")
                message = error.get("Message", "unknown error")
                raise HiagentAPIError(f"Hiagent API {action} error {code}: {message}")
            raise HiagentAPIError(f"Hiagent API {action} error: {error}")
        if getattr(response, "status_code", 0) >= 400:
            raise HiagentAPIError(
                f"Hiagent API {action} HTTP {response.status_code}: {response.text}"
            )
        result = data.get("Result", data)
        if not isinstance(result, dict):
            raise HiagentAPIError(f"Hiagent API {action} returned non-object Result")
        return result

    def check_app_by_name(self, name: str) -> bool:
        result = self._post(
            "CheckAppByName",
            {"WorkspaceID": self.workspace_id, "Name": name},
        )
        return bool(result.get("Reduplicated", False))

    def create_app(
        self,
        *,
        name: str,
        app_type: str,
        description: str,
        icon: str = "",
    ) -> str:
        result = self._post(
            "CreateApp",
            {
                "WorkspaceID": self.workspace_id,
                "Name": name,
                "AppType": app_type,
                "Icon": icon,
                "Description": description,
            },
        )
        app_id = result.get("AppID")
        if not isinstance(app_id, str) or not app_id:
            raise HiagentAPIError("CreateApp response missing AppID")
        return app_id

    def get_chatflow(self, app_id: str, *, with_node: bool = True) -> dict[str, Any]:
        result = self._post(
            "GetChatflow",
            {
                "WorkspaceID": self.workspace_id,
                "AppID": app_id,
                "WithNode": with_node,
            },
        )
        return result

    def create_chatflow_node(
        self,
        app_id: str,
        *,
        node_type: str,
        layout: dict[str, Any],
        name: str = "",
    ) -> dict[str, Any]:
        result = self._post(
            "CreateChatFlowNode",
            {
                "WorkspaceID": self.workspace_id,
                "AppID": app_id,
                "Type": node_type,
                "Layout": layout,
                "Name": name,
            },
        )
        node = result.get("Node")
        if not isinstance(node, dict):
            raise HiagentAPIError("CreateChatFlowNode response missing Node")
        return node

    def save_chatflow(
        self,
        app_id: str,
        *,
        nodes: list[dict[str, Any]],
        links: list[dict[str, Any]],
    ) -> None:
        self._post(
            "SaveChatflow",
            {
                "WorkspaceID": self.workspace_id,
                "AppID": app_id,
                "Nodes": nodes,
                "Links": links,
            },
        )

    def list_workspace_models(self) -> list[dict[str, Any]]:
        """Return models granted to the current workspace.

        App actions use TOP service `app`, but model-management actions are
        routed by Hiagent's frontend through `/api/aigw` and must be signed
        with TOP service `aigw`.
        """
        result = self._post(
            "ListModelByWorkspaceGrant",
            {
                "WorkspaceID": self.workspace_id,
                "Filter": {"IsGranted": True},
                "ListOpt": {
                    "PageSize": 40,
                    "PageNumber": 1,
                    "Sort": [{"SortField": "created_at", "SortOrder": "desc"}],
                },
            },
            service="aigw",
        )
        items = result.get("Items", [])
        if not isinstance(items, list):
            raise HiagentAPIError("ListModelByWorkspaceGrant response Items is not a list")
        return [item for item in items if isinstance(item, dict)]

    def list_workspace_datasets(self) -> list[dict[str, Any]]:
        result = self._post(
            "ListDatasets",
            {
                "WorkspaceID": self.workspace_id,
                "PageNumber": 1,
                "PageSize": 40,
            },
        )
        items = result.get("Items", [])
        if not isinstance(items, list):
            raise HiagentAPIError("ListDatasets response Items is not a list")
        return [item for item in items if isinstance(item, dict)]

    def resolve_default_dataset_id(self) -> str | None:
        env_dataset = os.environ.get("HIAGENT_DATASET_ID")
        if env_dataset:
            return env_dataset
        datasets = [
            dataset
            for dataset in self.list_workspace_datasets()
            if isinstance(dataset.get("Id"), str) or isinstance(dataset.get("ID"), str)
        ]
        if not datasets:
            return None
        first = datasets[0]
        dataset_id = first.get("Id") or first.get("ID")
        return str(dataset_id)

    def resolve_default_text_generation_model_id(self) -> str | None:
        """Pick a usable text-generation model for API-created Chat apps."""
        env_model = os.environ.get("HIAGENT_MODEL_ID")
        if env_model:
            return env_model
        models = [
            model
            for model in self.list_workspace_models()
            if model.get("Type") == "text-generation" and isinstance(model.get("ID"), str)
        ]
        for model in models:
            if model.get("IsDefault"):
                return str(model["ID"])
        if models:
            return str(models[0]["ID"])
        return None

    def save_app_config_draft(self, app_id: str, config_draft: dict[str, Any]) -> None:
        self._post(
            "SaveAppConfigDraft",
            {
                "WorkspaceID": self.workspace_id,
                "AppID": app_id,
                "AppConfigDraft": config_draft,
            },
        )

    def save_chatflow_config_draft(
        self,
        app_id: str,
        chatflow_config: dict[str, Any],
    ) -> None:
        self._post(
            "SaveChatFlowConfigDraft",
            {
                "WorkspaceID": self.workspace_id,
                "AppID": app_id,
                "ChatFlowConfig": chatflow_config,
            },
        )

    def publish_app_v2(
        self,
        app_id: str,
        *,
        app_config: dict[str, Any] | None = None,
        chatflow_config: dict[str, Any] | None = None,
        agent_mode: str = "Single",
        version: str = "v1.0.0",
    ) -> str:
        if (app_config is None) == (chatflow_config is None):
            raise HiagentAPIError(
                "PublishAppV2 requires exactly one of app_config or chatflow_config"
            )
        payload: dict[str, Any] = {
            "WorkspaceID": self.workspace_id,
            "AppID": app_id,
            "AgentMode": agent_mode,
        }
        if app_config is not None:
            payload["AppConfig"] = {**app_config, "Version": version}
        if chatflow_config is not None:
            payload["ChatFlowConfig"] = {**chatflow_config, "Version": version}
        result = self._post(
            "PublishAppV2",
            payload,
        )
        publish_id = result.get("PublishID") or result.get("VersionCode")
        if not isinstance(publish_id, str) or not publish_id:
            raise HiagentAPIError("PublishAppV2 response missing PublishID")
        return publish_id

    def app_url(self, app_id: str) -> str:
        parsed = urlparse(self.base_url)
        host = parsed.hostname or parsed.netloc
        if not host:
            host = parsed.netloc
        scheme = parsed.scheme or "http"
        return f"{scheme}://{host}/workspace/{self.workspace_id}/agent/{app_id}"


def _normalize_top_base_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise HiagentAPIError("empty Hiagent base URL")
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    hostname = parsed.hostname
    if not hostname:
        raise HiagentAPIError(f"invalid Hiagent base URL: {raw!r}")
    port = parsed.port or _DEFAULT_TOP_PORT
    netloc = f"{hostname}:{port}"
    return urlunparse((scheme, netloc, "", "", "", ""))


def _norm_uri(path: str) -> str:
    return quote(path).replace("%2F", "/").replace("+", "%20")


def _norm_query(query: dict[str, str]) -> str:
    parts: list[str] = []
    for key in sorted(query):
        parts.append(
            quote(key, safe="-_.~") + "=" + quote(str(query[key]), safe="-_.~")
        )
    return "&".join(parts).replace("+", "%20")


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(sk: str, date: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(sk.encode("utf-8"), date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "request")
