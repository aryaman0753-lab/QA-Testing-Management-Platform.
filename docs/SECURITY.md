# Security review

Phase 6 reviewed the major application boundaries:

| Area | Control |
|---|---|
| Authentication | Expiring signed JWTs; hashed passwords; project CI keys hashed, scoped, expiring/revocable |
| Authorization/IDOR | Central current-user dependency; project membership checks; nested resources verified against projects; admin operations restricted |
| SQL injection | SQLAlchemy expressions and fixed health/migration queries; no user-built SQL |
| XSS | React escaping; downloadable reports use attachment disposition; no raw HTML rendering |
| CSRF | Bearer tokens are not ambient cookies; exact CORS origins; do not migrate auth to cookies without CSRF tokens |
| SSRF | API/load controls retained; webhooks require HTTPS, public DNS/IP, peer pinning, no redirects or URL credentials |
| Uploads | Size limit, extension allowlist, magic-byte/MIME validation, safe basename, UUID storage path, authorized download, executable formats rejected |
| Secrets | Encryption at rest for request/webhook secrets; API keys hashed; masking in reports/API; structured-log redaction |
| Abuse | Redis rate limits on login, CI, execution, and webhook configuration; production fallback limiter; request-size ceiling |
| Browser | nosniff, deny framing, no-referrer, permissions policy, and production HSTS headers |
| Isolation | PostgreSQL/Redis are internal in production Compose; each worker rechecks execution policy |

Remaining deployment responsibilities: TLS and network policies at ingress, secret-manager injection, dependency/container scanning, SMTP certificate policy, `/metrics` network restriction, and log-retention/access policy. Rate limiting is process-local only as a safety fallback when production Redis is down; keep Redis highly available.
