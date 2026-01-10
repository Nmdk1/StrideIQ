#!/bin/bash
set -e

echo "Waiting for database to be ready..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-running_app}"; do
  echo "Database is unavailable - sleeping"
  sleep 1
done

echo "Running migrations..."
alembic upgrade head

echo "Migrations completed!"




