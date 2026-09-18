# QAHub production checklist

## Security

- [ ] Unique JWT, encryption, database, SMTP, CI, and webhook secrets configured in a secret manager
- [ ] Exact HTTPS CORS origins configured
- [ ] HTTPS termination and production HSTS verified
- [ ] Redis-backed rate limits enabled and load tested
- [ ] SSRF protection and allowlists verified from the production network
- [ ] Production automation/load restrictions enabled only when explicitly approved
- [ ] Upload limits, attachment backup, malware policy, and authorized download tested
- [ ] `/metrics`, database, Redis, and admin routes restricted to intended networks/users

## Database

- [ ] `alembic upgrade head` completed and current revision is `0006`
- [ ] Automated encrypted PostgreSQL and attachment backups configured
- [ ] Restore tested in an isolated environment with application-level verification
- [ ] Explicit retention values approved; cleanup impact reviewed

## Workers

- [ ] Automation worker running and heartbeating
- [ ] Scheduler worker running and heartbeating
- [ ] Load worker running and heartbeating
- [ ] Operations/webhook/email worker running and heartbeating
- [ ] Concurrency and resource limits sized from measured workloads

## Monitoring

- [ ] `/health/live` and `/health/ready` monitored separately
- [ ] Structured logs collected with request-ID search
- [ ] Prometheus `/metrics` scraped and Grafana/alerts configured
- [ ] Worker unavailability, queue depth, failed jobs, and failed deliveries alerting tested

## CI/CD

- [ ] Project CI API keys created separately per provider and stored as protected secrets
- [ ] Key expiry/revocation procedure tested
- [ ] Pipeline handles CLI exit codes 0/1/2 correctly
- [ ] Signed webhook consumer validates raw body and deduplicates delivery IDs

## Notifications

- [ ] SMTP TLS, sender, authentication, and delivery tested from operations worker
- [ ] User/project notification preferences tested
- [ ] Duplicate suppression and failure visibility verified

## Release

- [ ] Backend tests, frontend tests, frontend production build, and migration upgrade pass
- [ ] Docker production configuration validates with deployment environment
- [ ] Rollback compatibility and data recovery point approved
- [ ] Manual CI → webhook → report workflow completed
