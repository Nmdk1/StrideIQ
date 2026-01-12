#!/usr/bin/env python3
"""
PostgreSQL Database Backup Script

Automated backup for production database.
Run via cron or scheduled task.

Usage:
    python backup_database.py                    # Backup to local directory
    python backup_database.py --s3 my-bucket     # Backup to S3
    python backup_database.py --retention 7      # Keep only last 7 days

Environment Variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (for S3)
"""

import os
import sys
import subprocess
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BACKUP_DIR = Path("/backups")
DEFAULT_RETENTION_DAYS = 7


def get_db_config():
    """Get database configuration from environment."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "database": os.getenv("POSTGRES_DB", "running_app"),
    }


def create_backup(backup_dir: Path) -> Path:
    """
    Create a PostgreSQL backup using pg_dump.
    
    Returns:
        Path to the backup file
    """
    config = get_db_config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{config['database']}_{timestamp}.sql.gz"
    
    # Ensure backup directory exists
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Set PGPASSWORD for pg_dump
    env = os.environ.copy()
    env["PGPASSWORD"] = config["password"]
    
    # Build pg_dump command
    cmd = [
        "pg_dump",
        "-h", config["host"],
        "-p", config["port"],
        "-U", config["user"],
        "-d", config["database"],
        "--format=plain",
        "--no-owner",
        "--no-acl",
    ]
    
    logger.info(f"Starting backup of {config['database']}...")
    
    try:
        # Run pg_dump and pipe through gzip
        with open(backup_file, "wb") as f:
            pg_dump = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            gzip = subprocess.Popen(
                ["gzip", "-c"],
                stdin=pg_dump.stdout,
                stdout=f,
                stderr=subprocess.PIPE
            )
            pg_dump.stdout.close()
            gzip.communicate()
            
            if pg_dump.wait() != 0:
                stderr = pg_dump.stderr.read().decode()
                raise Exception(f"pg_dump failed: {stderr}")
        
        # Verify file was created
        if not backup_file.exists() or backup_file.stat().st_size == 0:
            raise Exception("Backup file is empty or was not created")
        
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        logger.info(f"Backup created: {backup_file} ({size_mb:.2f} MB)")
        
        return backup_file
        
    except FileNotFoundError as e:
        logger.error(f"Required tool not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        # Clean up partial file
        if backup_file.exists():
            backup_file.unlink()
        raise


def upload_to_s3(backup_file: Path, bucket: str, prefix: str = "backups/"):
    """
    Upload backup file to S3.
    
    Args:
        backup_file: Path to local backup file
        bucket: S3 bucket name
        prefix: S3 key prefix
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        logger.error("boto3 not installed. Run: pip install boto3")
        raise
    
    s3_key = f"{prefix}{backup_file.name}"
    
    logger.info(f"Uploading to s3://{bucket}/{s3_key}...")
    
    try:
        s3 = boto3.client("s3")
        s3.upload_file(str(backup_file), bucket, s3_key)
        logger.info(f"Upload complete: s3://{bucket}/{s3_key}")
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise


def cleanup_old_backups(backup_dir: Path, retention_days: int):
    """
    Remove backup files older than retention period.
    
    Args:
        backup_dir: Directory containing backups
        retention_days: Number of days to keep
    """
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed_count = 0
    
    for backup_file in backup_dir.glob("*.sql.gz"):
        if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff:
            logger.info(f"Removing old backup: {backup_file.name}")
            backup_file.unlink()
            removed_count += 1
    
    logger.info(f"Cleanup complete: removed {removed_count} old backup(s)")


def verify_backup(backup_file: Path) -> bool:
    """
    Verify backup file is valid by checking gzip integrity.
    
    Args:
        backup_file: Path to backup file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        result = subprocess.run(
            ["gzip", "-t", str(backup_file)],
            capture_output=True
        )
        if result.returncode == 0:
            logger.info("Backup verification: PASSED")
            return True
        else:
            logger.error(f"Backup verification: FAILED - {result.stderr.decode()}")
            return False
    except Exception as e:
        logger.error(f"Backup verification error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="PostgreSQL database backup utility"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help=f"Local backup directory (default: {DEFAULT_BACKUP_DIR})"
    )
    parser.add_argument(
        "--s3",
        metavar="BUCKET",
        help="Upload to S3 bucket"
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Days to keep local backups (default: {DEFAULT_RETENTION_DAYS})"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify backup after creation"
    )
    
    args = parser.parse_args()
    
    try:
        # Create backup
        backup_file = create_backup(args.backup_dir)
        
        # Verify if requested
        if args.verify:
            if not verify_backup(backup_file):
                sys.exit(1)
        
        # Upload to S3 if specified
        if args.s3:
            upload_to_s3(backup_file, args.s3)
        
        # Cleanup old backups
        cleanup_old_backups(args.backup_dir, args.retention)
        
        logger.info("Backup completed successfully")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
