# QAHub CLI

Install the local CLI in an activated virtual environment:

```bash
pip install -e backend --no-deps
qahub login --url https://qahub.example.com --email engineer@example.com
```

Authentication can come from the saved login, `QAHUB_TOKEN`, or a project CI key in `QAHUB_API_KEY`. Suite and environment names are resolved for both login and CI-key modes; use `--project` when a suite name exists in more than one accessible project. CI keys are preferred in pipelines and must be stored in the provider's secret store.

```bash
qahub test run 7d2... --environment 4a1...
qahub test run --suite smoke-tests --project SHOP --environment staging --provider github --commit-sha "$GITHUB_SHA" --build-number "$GITHUB_RUN_NUMBER"
qahub test status RUN_ID
qahub test wait RUN_ID --timeout 1800
qahub test export RUN_ID --format json --output result.json
```

`test run` waits by default; add `--no-wait` to return after acceptance. Exit code `0` means passed, `1` means failed/cancelled, and `2` means non-terminal, timeout, configuration, authentication, or connectivity error. The CLI never prints API keys or login passwords. The login token file is created with user-only permissions where the OS supports it; use short-lived tokens or environment injection on shared runners.
