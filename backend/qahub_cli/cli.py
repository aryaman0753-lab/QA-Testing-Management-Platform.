"""Dependency-free QAHub CI client with stable pipeline exit codes."""
import argparse
import csv
import getpass
import io
import json
import os
from pathlib import Path
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PASSED = {"PASSED", "PASS", "COMPLETED"}
FAILED = {"FAILED", "FAIL", "CANCELLED", "ERROR", "THRESHOLD_EXCEEDED"}
TERMINAL = PASSED | FAILED


class CliError(Exception): pass


def _config_path() -> Path:
    custom = os.environ.get("QAHUB_CONFIG")
    return Path(custom).expanduser() if custom else Path.home() / ".config" / "qahub" / "config.json"


def _load() -> dict:
    try: return json.loads(_config_path().read_text(encoding="utf-8"))
    except FileNotFoundError: return {}
    except (OSError, json.JSONDecodeError) as exc: raise CliError("QAHub CLI configuration is unreadable.") from exc


def _save(config: dict) -> None:
    path = _config_path(); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    try: path.chmod(0o600)
    except OSError: pass


def _base(config: dict) -> str:
    return (os.environ.get("QAHUB_URL") or config.get("url") or "http://localhost:8000").rstrip("/")


def _request(config: dict, method: str, path: str, payload=None, api_key=False):
    headers = {"Accept": "application/json", "User-Agent": "qahub-cli/0.6.0"}
    if payload is not None: headers["Content-Type"] = "application/json"
    key = os.environ.get("QAHUB_API_KEY")
    token = os.environ.get("QAHUB_TOKEN") or config.get("token")
    if api_key:
        if not key: raise CliError("Set QAHUB_API_KEY to trigger or inspect CI runs.")
        headers["X-QAHub-API-Key"] = key
    elif token: headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        with urlopen(Request(_base(config) + path, data=body, headers=headers, method=method), timeout=30) as response:
            return json.loads(response.read() or b"{}")
    except HTTPError as exc:
        try: message = json.loads(exc.read()).get("error", {}).get("message")
        except Exception: message = None
        raise CliError(message or f"QAHub returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc: raise CliError("Could not connect to QAHub.") from exc


def _status_code(value: str) -> int:
    if value in PASSED: return 0
    if value in FAILED: return 1
    return 2


def _status(config: dict, run_id: str) -> dict:
    if os.environ.get("QAHUB_API_KEY"): return _request(config, "GET", f"/api/v1/ci/test-runs/{run_id}", api_key=True)
    if not (os.environ.get("QAHUB_TOKEN") or config.get("token")): raise CliError("Run `qahub login` or set QAHUB_API_KEY.")
    return _request(config, "GET", f"/api/v1/automation/runs/{run_id}")


def _uuid(value: str | None) -> bool:
    try: uuid.UUID(value or ""); return True
    except ValueError: return False


def _resolve_jwt_run(config: dict, suite: str, project_hint: str | None, environment: str | None) -> tuple[str, str | None]:
    projects = _request(config, "GET", "/api/v1/projects")
    if project_hint:
        projects = [row for row in projects if project_hint in {row.get("id"), row.get("key"), row.get("name")}]
        if not projects: raise CliError("Project not found or not accessible.")
    candidates = []
    if _uuid(suite):
        detail = _request(config, "GET", f"/api/v1/automation/suites/{suite}")
        if project_hint and str(detail["project_id"]) not in {str(row["id"]) for row in projects}:
            raise CliError("Suite does not belong to the selected project.")
        candidates = [(str(detail["id"]), str(detail["project_id"]))]
    else:
        for project in projects:
            page = 1
            while True:
                response = _request(config, "GET", f"/api/v1/projects/{project['id']}/automation/suites?page={page}&page_size=100")
                candidates.extend((str(row["id"]), str(project["id"])) for row in response.get("items", []) if row.get("name") == suite)
                if page >= response.get("total_pages", 1): break
                page += 1
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        raise CliError("Suite name is missing or ambiguous; supply --project or a suite UUID.")
    suite_id, project_id = candidates[0]
    if not environment or _uuid(environment): return suite_id, environment
    rows = _request(config, "GET", f"/api/v1/projects/{project_id}/api/environments")
    matches = [str(row["id"]) for row in rows if row.get("name") == environment]
    if len(matches) != 1: raise CliError("Environment name is missing or ambiguous in the suite project.")
    return suite_id, matches[0]


def _wait(config: dict, run_id: str, timeout: int, interval: float) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        value = _status(config, run_id); status = value.get("status", "UNKNOWN").upper()
        print(f"{run_id}: {status}", file=sys.stderr)
        if status in TERMINAL: return value
        if time.monotonic() >= deadline: raise CliError(f"Timed out after {timeout} seconds while waiting for the run.")
        time.sleep(interval)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="qahub", description="Trigger and monitor QAHub automation from a terminal or CI job.")
    commands = root.add_subparsers(dest="command", required=True)
    login = commands.add_parser("login"); login.add_argument("--url"); login.add_argument("--email", required=True); login.add_argument("--password")
    test = commands.add_parser("test"); tests = test.add_subparsers(dest="test_command", required=True)
    run = tests.add_parser("run"); run.add_argument("suite_id", nargs="?"); run.add_argument("--suite"); run.add_argument("--project"); run.add_argument("--environment"); run.add_argument("--commit-sha"); run.add_argument("--branch"); run.add_argument("--build-number"); run.add_argument("--provider", default="generic"); run.add_argument("--metadata", default="{}"); run.add_argument("--no-wait", action="store_true"); run.add_argument("--timeout", type=int, default=1800); run.add_argument("--interval", type=float, default=2)
    status = tests.add_parser("status"); status.add_argument("run_id")
    wait = tests.add_parser("wait"); wait.add_argument("run_id"); wait.add_argument("--timeout", type=int, default=1800); wait.add_argument("--interval", type=float, default=2)
    export = tests.add_parser("export"); export.add_argument("run_id"); export.add_argument("--format", choices=["json", "csv"], default="json"); export.add_argument("--output")
    return root


def _render(value: dict, format: str) -> str:
    if format == "json": return json.dumps(value, indent=2, default=str) + "\n"
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(["field", "value"])
    for key, item in value.items(): writer.writerow([key, json.dumps(item, default=str) if isinstance(item, (dict, list)) else item])
    return stream.getvalue()


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        config = _load()
        if args.command == "login":
            if args.url: config["url"] = args.url.rstrip("/")
            password = args.password or getpass.getpass("Password: ")
            result = _request(config, "POST", "/api/v1/auth/login", {"email": args.email, "password": password})
            config["token"] = result["access_token"]; _save(config); print(f"Logged in as {result['user']['email']}"); return 0
        if args.test_command == "run":
            suite = args.suite or args.suite_id
            if not suite: raise CliError("Provide a suite ID or --suite name.")
            if os.environ.get("QAHUB_API_KEY"):
                try: metadata = json.loads(args.metadata)
                except json.JSONDecodeError as exc: raise CliError("--metadata must be a JSON object.") from exc
                if not isinstance(metadata, dict): raise CliError("--metadata must be a JSON object.")
                result = _request(config, "POST", "/api/v1/ci/test-runs", {"project": args.project, "suite": suite, "environment": args.environment, "commit_sha": args.commit_sha, "branch": args.branch, "build_number": args.build_number, "ci_provider": args.provider, "metadata": metadata}, api_key=True)
            else:
                suite_id, environment_id = _resolve_jwt_run(config, suite, args.project, args.environment)
                result = _request(config, "POST", f"/api/v1/automation/suites/{suite_id}/run", {"environment_id": environment_id, "confirm_production": False})
            run_id = str(result.get("run_id") or result.get("id")); print(json.dumps(result, default=str))
            if args.no_wait: return 0
            final = _wait(config, run_id, args.timeout, args.interval); return _status_code(final.get("status", ""))
        if args.test_command == "status":
            result = _status(config, args.run_id); print(json.dumps(result, indent=2, default=str)); return _status_code(result.get("status", ""))
        if args.test_command == "wait":
            result = _wait(config, args.run_id, args.timeout, args.interval); print(json.dumps(result, indent=2, default=str)); return _status_code(result.get("status", ""))
        result = _status(config, args.run_id); rendered = _render(result, args.format)
        if args.output: Path(args.output).write_text(rendered, encoding="utf-8")
        else: print(rendered, end="")
        return _status_code(result.get("status", ""))
    except (CliError, KeyError, ValueError) as exc:
        print(f"qahub: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
