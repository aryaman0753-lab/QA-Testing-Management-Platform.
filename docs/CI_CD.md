# CI/CD integration

Create a project key under **CI & Webhooks**, copy it once, and save it as a protected CI secret. Trigger with `POST /api/v1/ci/test-runs` and `X-QAHub-API-Key`. Suite/environment accept UUIDs or names. Poll `GET /api/v1/ci/test-runs/{run_id}`. Keys are project-scoped, hashed at rest, revocable, optionally expiring, and rate-limited.

Request example:

```json
{"project":"SHOP","suite":"smoke-tests","environment":"staging","commit_sha":"abc123","branch":"main","build_number":"42","ci_provider":"github","metadata":{"pull_request":17}}
```

GitHub Actions:

```yaml
- name: QAHub smoke suite
  env:
    QAHUB_URL: https://qahub.example.com
    QAHUB_API_KEY: ${{ secrets.QAHUB_API_KEY }}
  run: |
    pip install -e backend --no-deps
    qahub test run --suite smoke-tests --project SHOP --environment staging --provider github --commit-sha "$GITHUB_SHA" --branch "$GITHUB_REF_NAME" --build-number "$GITHUB_RUN_NUMBER"
```

GitLab CI:

```yaml
qahub:
  script:
    - pip install -e backend --no-deps
    - qahub test run --suite smoke-tests --project SHOP --environment staging --provider gitlab --commit-sha "$CI_COMMIT_SHA" --branch "$CI_COMMIT_REF_NAME" --build-number "$CI_PIPELINE_ID"
```

Jenkins:

```groovy
withCredentials([string(credentialsId: 'qahub-api-key', variable: 'QAHUB_API_KEY')]) {
  sh 'pip install -e backend --no-deps'
  sh 'qahub test run --suite smoke-tests --project SHOP --environment staging --provider jenkins --commit-sha "$GIT_COMMIT" --branch "$BRANCH_NAME" --build-number "$BUILD_NUMBER"'
}
```

Azure Pipelines:

```yaml
- script: |
    pip install -e backend --no-deps
    qahub test run --suite smoke-tests --project SHOP --environment staging --provider azure --commit-sha "$(Build.SourceVersion)" --branch "$(Build.SourceBranchName)" --build-number "$(Build.BuildNumber)"
  env:
    QAHUB_URL: https://qahub.example.com
    QAHUB_API_KEY: $(QAHUB_API_KEY)
```

Protect variables from forked/untrusted jobs. Use separate keys per provider so revocation and audit attribution remain clear.
