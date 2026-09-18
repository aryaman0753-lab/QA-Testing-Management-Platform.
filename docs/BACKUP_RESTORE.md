# PostgreSQL backup and restore

Run backups from a protected host or the database container with credentials supplied securely:

```bash
pg_dump --format=custom --no-owner --file=qahub-$(date +%F-%H%M).dump "$DATABASE_URL"
pg_restore --list qahub-YYYY-MM-DD-HHMM.dump
```

Schedule example (daily at 02:15, with output monitored):

```cron
15 2 * * * /opt/qahub/bin/backup-qahub >>/var/log/qahub-backup.log 2>&1
```

Store encrypted copies outside the application host and apply separate retention/access controls. Attachments are outside PostgreSQL and require their own snapshot/object-storage backup synchronized with the database recovery point.

Restore into a new, empty verification database first:

```bash
createdb qahub_restore_verify
pg_restore --clean --if-exists --no-owner --dbname=qahub_restore_verify qahub-YYYY-MM-DD-HHMM.dump
psql qahub_restore_verify -c 'select version_num from alembic_version;'
psql qahub_restore_verify -c 'select count(*) from projects;'
```

Start a QAHub API against that isolated database, run `/health/ready` (with test Redis), authenticate, inspect several projects/runs/attachments, and execute integrity queries. Record restore duration and evidence. A successful `pg_dump` exit alone is not backup verification.
