# Database Backup and Restore Procedures

## Overview

This document describes the backup and restore procedures for the StrideIQ PostgreSQL database.

## Backup Strategy

- **Frequency**: Daily at 3 AM
- **Retention**: 7 days locally, 30 days in S3
- **Format**: gzip-compressed SQL dumps
- **Location**: `/backups/` directory or S3 bucket

## Creating a Backup

### Manual Backup (Docker)

```bash
# Quick backup
docker-compose exec postgres pg_dump -U postgres running_app | gzip > backup_$(date +%Y%m%d).sql.gz

# With the backup script
python scripts/backup_database.py --backup-dir ./backups --verify
```

### Manual Backup (Direct)

```bash
PGPASSWORD=your_password pg_dump -h localhost -U postgres -d running_app | gzip > backup.sql.gz
```

### Automated Backup (Cron)

Add to crontab:
```bash
# Daily at 3 AM
0 3 * * * /path/to/scripts/backup_cron.sh >> /var/log/backup.log 2>&1

# With S3 upload
0 3 * * * python /path/to/scripts/backup_database.py --s3 strideiq-backups --retention 7
```

## Restoring from Backup

### Restore to Existing Database

```bash
# Stop the application first
docker-compose stop api worker

# Restore
gunzip -c backup_20260111.sql.gz | docker-compose exec -T postgres psql -U postgres -d running_app

# Restart
docker-compose start api worker
```

### Restore to Fresh Database

```bash
# Create new database
docker-compose exec postgres createdb -U postgres running_app_restored

# Restore
gunzip -c backup_20260111.sql.gz | docker-compose exec -T postgres psql -U postgres -d running_app_restored

# Verify
docker-compose exec postgres psql -U postgres -d running_app_restored -c "\dt"
```

### Restore from S3

```bash
# Download from S3
aws s3 cp s3://strideiq-backups/backups/running_app_20260111_030000.sql.gz .

# Restore
gunzip -c running_app_20260111_030000.sql.gz | docker-compose exec -T postgres psql -U postgres -d running_app
```

## Verification

### Check Backup Integrity

```bash
# Verify gzip file
gzip -t backup.sql.gz && echo "OK" || echo "CORRUPTED"

# Check backup contents (list tables)
gunzip -c backup.sql.gz | grep "CREATE TABLE" | head -20
```

### Test Restore

```bash
# Create test database
docker-compose exec postgres createdb -U postgres restore_test

# Restore
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U postgres -d restore_test

# Verify row counts
docker-compose exec postgres psql -U postgres -d restore_test -c "SELECT 'athletes' as table_name, count(*) FROM athletes UNION ALL SELECT 'activities', count(*) FROM activities;"

# Cleanup
docker-compose exec postgres dropdb -U postgres restore_test
```

## Disaster Recovery

### Complete System Recovery

1. **Provision new infrastructure**
   - Spin up PostgreSQL, Redis, API servers

2. **Restore database**
   ```bash
   aws s3 cp s3://strideiq-backups/backups/LATEST.sql.gz .
   gunzip -c LATEST.sql.gz | psql -U postgres -d running_app
   ```

3. **Run migrations** (if any pending)
   ```bash
   cd apps/api && alembic upgrade head
   ```

4. **Verify application**
   ```bash
   curl http://localhost:8000/health
   ```

5. **Update DNS** (if needed)

### Recovery Time Objectives

| Scenario | RTO | RPO |
|----------|-----|-----|
| Database corruption | 1 hour | 24 hours |
| Full infrastructure failure | 4 hours | 24 hours |
| Accidental data deletion | 30 min | 24 hours |

## Monitoring

### Backup Health Checks

```bash
# Check latest backup age
find /backups -name "*.sql.gz" -mtime -1 | wc -l  # Should be >= 1

# Check backup size (should be > 0)
ls -la /backups/*.sql.gz | tail -1
```

### Alerts

Set up alerts for:
- [ ] No backup file created in 25 hours
- [ ] Backup file smaller than expected
- [ ] S3 upload failure
- [ ] Disk space < 10GB

## Security

- Backup files are encrypted at rest in S3
- Access restricted via IAM policies
- No passwords stored in backup files (uses `--no-owner --no-acl`)
- Backup server access logged

---

**Last Updated**: 2026-01-11
**Owner**: DevOps Team
