#!/bin/sh
set -eu

: "${PORT:=8000}"

echo "Applying tenant database migrations..."
alembic upgrade head

echo "Applying control-plane database migrations..."
alembic -c control_alembic.ini upgrade head

echo "Starting MiniTally API on port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
