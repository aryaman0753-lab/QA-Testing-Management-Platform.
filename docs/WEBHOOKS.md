# Webhooks

Supported events are `automation.run.started`, `automation.run.completed`, `automation.run.failed`, `load_test.completed`, `load_test.failed`, `bug.created`, and `bug.updated`.

QAHub accepts only HTTPS destinations without URL credentials, query strings, or fragments and re-validates DNS immediately before each connection. Put receiver authentication in the write-only signing secret. Private, loopback, local, reserved, and multicast destinations are rejected. Redirects are not followed.

Each JSON request has these headers:

- `X-QAHub-Event`
- `X-QAHub-Delivery`
- `X-QAHub-Signature-256: sha256=<hex digest>`

Verify the raw request body before parsing:

```python
expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, signature_header):
    abort(401)
```

Return any 2xx status to acknowledge. QAHub times out after `WEBHOOK_TIMEOUT_SECONDS`, does not retry successful deliveries, and retries failures after 30, 60, 120… seconds up to `WEBHOOK_MAX_ATTEMPTS` (one hour maximum delay). Delivery history records status, response code, safe failure reason, attempts, and next retry; it never returns payloads or secrets to the browser. Consumers should deduplicate using `X-QAHub-Delivery`.
