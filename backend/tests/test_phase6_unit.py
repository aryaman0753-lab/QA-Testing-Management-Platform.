import hashlib
import hmac
import json
from types import SimpleNamespace

from qahub_cli import cli
from app.operations.providers import EmailNotificationProvider
from workers.operations.worker import sign_payload


def test_webhook_signature_is_over_canonical_raw_body():
    body, signature = sign_payload("delivery-secret", {"event": "bug.created", "data": {"id": "1"}})
    assert json.loads(body) == {"event": "bug.created", "data": {"id": "1"}}
    expected = hmac.new(b"delivery-secret", body, hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected}"


def test_email_provider_uses_config_without_exposing_credentials(monkeypatch):
    calls = []
    class FakeSmtp:
        def __init__(self, host, port, timeout): calls.append((host, port, timeout))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self): calls.append("tls")
        def login(self, username, password): calls.append((username, password))
        def send_message(self, message): calls.append((message["To"], message["Subject"]))
    monkeypatch.setattr("app.operations.providers.get_settings", lambda: SimpleNamespace(SMTP_HOST="smtp.example.com", SMTP_PORT=587, SMTP_FROM="qahub@example.com", SMTP_USE_TLS=True, SMTP_USERNAME="user", SMTP_PASSWORD="secret"))
    monkeypatch.setattr("app.operations.providers.smtplib.SMTP", FakeSmtp)
    EmailNotificationProvider().send("qa@example.com", "Run failed", "Inspect the run.")
    assert calls == [("smtp.example.com", 587, 15), "tls", ("user", "secret"), ("qa@example.com", "Run failed")]


def test_cli_exit_codes_and_ci_trigger(monkeypatch, tmp_path):
    monkeypatch.setenv("QAHUB_CONFIG", str(tmp_path / "config.json")); monkeypatch.setenv("QAHUB_API_KEY", "qh_test")
    responses = iter([{"run_id": "run-1", "status": "QUEUED"}, {"run_id": "run-1", "status": "PASSED"}])
    monkeypatch.setattr(cli, "_request", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    assert cli.main(["test", "run", "--suite", "smoke", "--project", "SHOP"]) == 0
    monkeypatch.setattr(cli, "_status", lambda *_: {"status": "FAILED"})
    assert cli.main(["test", "status", "run-2"]) == 1


def test_cli_resolves_suite_and_environment_names_for_login_token(monkeypatch, tmp_path):
    monkeypatch.setenv("QAHUB_CONFIG", str(tmp_path / "config.json")); monkeypatch.setenv("QAHUB_TOKEN", "jwt-test"); monkeypatch.delenv("QAHUB_API_KEY", raising=False)
    posts = []
    def request(config, method, path, payload=None, api_key=False):
        if path == "/api/v1/projects": return [{"id": "11111111-1111-1111-1111-111111111111", "key": "SHOP", "name": "Shop"}]
        if "/automation/suites?" in path: return {"items": [{"id": "22222222-2222-2222-2222-222222222222", "name": "smoke"}], "total_pages": 1}
        if path.endswith("/api/environments"): return [{"id": "33333333-3333-3333-3333-333333333333", "name": "staging"}]
        posts.append((path, payload)); return {"id": "run-3", "status": "QUEUED"}
    monkeypatch.setattr(cli, "_request", request)
    assert cli.main(["test", "run", "--suite", "smoke", "--project", "SHOP", "--environment", "staging", "--no-wait"]) == 0
    assert posts[0][0].endswith("22222222-2222-2222-2222-222222222222/run")
    assert posts[0][1]["environment_id"] == "33333333-3333-3333-3333-333333333333"
