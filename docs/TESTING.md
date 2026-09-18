# Test strategy

Backend tests cover authentication/RBAC, project isolation, bugs and secure uploads, API testing, load thresholds/baselines, automation execution/scheduling, CI credentials/triggers, webhook persistence/secret masking, notifications, reports, admin monitoring, and the error contract. Worker engine tests use deterministic fakes so they do not generate real load or contact arbitrary networks.

Frontend Vitest tests cover components, forms, dashboards, filters, workflows, quality reporting, and empty/error states. Build validation catches strict TypeScript and route integration errors.

The manual end-to-end release scenario is: login → create project/environment/API request → create suite/case/step → execute and verify result → create/link bug → create CI key → trigger via CLI/CI API → receive and validate signed webhook → export JSON/CSV/PDF report. Run against an isolated test deployment and public controlled webhook receiver, never production targets.

```bash
cd backend && python -m pytest -q
cd frontend && npm test -- --run && npm run build
```
