import os

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.service.app import create_app
from loom.service.deps import Settings


def test_health_and_openapi(tmp_path):
    settings = Settings(data_dir=tmp_path, app_env="dev", fernet_key=Fernet.generate_key().decode())
    client = TestClient(create_app(settings=settings))

    assert client.get("/health").json() == {"ok": True}
    assert client.get("/v1/health").json() == {"ok": True}
    assert client.get("/openapi.json").json()["openapi"].startswith("3.")


def test_vite_dev_origin_gets_cors_header(tmp_path):
    settings = Settings(data_dir=tmp_path, app_env="dev", fernet_key=Fernet.generate_key().decode())
    client = TestClient(create_app(settings=settings))

    resp = client.options(
        "/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_prod_requires_fernet_key(tmp_path, monkeypatch):
    monkeypatch.delenv("LOOM_FERNET_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="LOOM_FERNET_KEY"):
        Settings.from_env()


def test_unset_app_env_requires_fernet_key(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOOM_FERNET_KEY", raising=False)
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="LOOM_FERNET_KEY"):
        Settings.from_env()


def test_data_dir_created_private(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", app_env="dev", fernet_key=Fernet.generate_key().decode())
    settings.ensure_data_dir()
    mode = os.stat(settings.data_dir).st_mode & 0o777
    assert mode == 0o700


def test_audit_retention_cap_loaded_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOOM_AUDIT_MAX_RETENTION_DAYS", "180")
    settings = Settings.from_env()
    assert settings.audit_max_retention_days == 180


def test_app_startup_fails_on_invalid_template_catalog(tmp_path, monkeypatch):
    from loom.registry.templates import TemplateCatalog, TemplateLoadError

    catalog_root = tmp_path / "templates"
    catalog_root.mkdir()
    (catalog_root / "index.json").write_text(
        """
        {
          "version": "sha:0000000",
          "templates": [{
            "id": "bad",
            "name": {"zh": "坏模板", "en": "Bad"},
            "description": {"zh": "坏", "en": "Bad"},
            "tags": [],
            "ir_file": "bad.yaml",
            "scopes": ["ecommerce/kb"],
            "compile_targets": ["hiagent"],
            "_internal_source": "test",
            "_internal_pattern": "bad"
          }]
        }
        """
    )
    (catalog_root / "bad.yaml").write_text("ir_version: [")
    original_load = TemplateCatalog.load
    monkeypatch.setattr(
        "loom.service.app.TemplateCatalog.load",
        lambda *_args, **_kwargs: original_load(catalog_root),
    )
    settings = Settings(data_dir=tmp_path / "data", app_env="dev", fernet_key=Fernet.generate_key().decode())

    with pytest.raises(TemplateLoadError, match="failed to load template bad"):
        create_app(settings=settings)
