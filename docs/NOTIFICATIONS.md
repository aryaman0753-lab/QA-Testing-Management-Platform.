# Notifications

Users can select in-app, email, and webhook channels globally or by project. Event filters suppress unwanted categories, and `(user, event ID)` uniqueness prevents duplicate in-app records.

Email uses the `NotificationProvider` abstraction and `EmailNotificationProvider`. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `SMTP_USE_TLS`. The API exposes only `email_configured`; it never returns SMTP credentials. Delivery happens in the operations worker, outside request processing. Failed email status is visible without exposing the server error or credentials.

Webhooks are configured per project rather than per user. Failure notifications cover automation, scheduled/CI automation, load tests, threshold violations, bug activity, and assignments/status changes emitted through the bug workflow.
