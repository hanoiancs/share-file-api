#!/bin/sh
set -e

# 1. Run migrations and advance schema state to latest revision
echo "Applying database migrations..."
uv run --env-file=.env alembic upgrade head

# 2. Hand off container execution context to CMD (FastAPI)
echo "Starting FastAPI application..."
exec "$@"