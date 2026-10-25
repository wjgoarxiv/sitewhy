from fastapi.testclient import TestClient

from app.config import Settings, load_settings
from app.main import create_app


def test_health_ok():
    client = TestClient(create_app(Settings()))
    assert client.get("/health").json() == {"status": "ok"}


def test_boots_unconfigured_and_reports_it(tmp_path):
    settings = load_settings(
        env={}, keys_file=tmp_path / "missing.env", nightshift_token_file=tmp_path / "missing-token"
    )
    client = TestClient(create_app(settings))
    assert client.get("/health").json() == {"status": "ok"}
    status = client.get("/status").json()
    assert status["nightshift"] == "not configured"
    assert status["zetaris"] == "not configured"
    assert status["sample_mode"] is False


def test_keys_file_and_token_file_are_read(tmp_path):
    keys = tmp_path / "keys.env"
    keys.write_text(
        "# comment\n"
        "ZETARIS_BASE_URL=http://localhost:3000\n"
        "ZETARIS_ORG_ID=1\n"
        "ZETARIS_API_KEY=abc\n"
        "broken line without equals\n"
    )
    token = tmp_path / "runtime-token"
    token.write_text("tok\n")
    s = load_settings(env={}, keys_file=keys, nightshift_token_file=token)
    assert s.zetaris_base_url == "http://localhost:3000"
    assert s.zetaris_org_id == "1"
    assert s.zetaris_api_key == "abc"
    assert s.nightshift_token == "tok"
    assert s.zetaris_configured and s.nightshift_configured


def test_env_overrides_keys_file(tmp_path):
    keys = tmp_path / "keys.env"
    keys.write_text("ZETARIS_ORG_ID=1\n")
    s = load_settings(
        env={"ZETARIS_ORG_ID": "7", "SAMPLE_MODE": "true"},
        keys_file=keys,
        nightshift_token_file=tmp_path / "none",
    )
    assert s.zetaris_org_id == "7"
    assert s.sample_mode is True


def test_secrets_never_appear_in_status(tmp_path):
    token = tmp_path / "runtime-token"
    token.write_text("super-secret-token")
    s = load_settings(
        env={"ZETARIS_API_KEY": "zkey-secret"},
        keys_file=tmp_path / "none",
        nightshift_token_file=token,
    )
    body = TestClient(create_app(s)).get("/status").text
    assert "super-secret-token" not in body and "zkey-secret" not in body
