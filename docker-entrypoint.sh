#!/bin/sh
set -e

# Apply any pending migrations on the Django app database.
# The vectors DB is read-only and is never migrated.
echo "[vectorbase] Running migrations..."
python manage.py migrate --noinput

echo "[vectorbase] Starting gunicorn (workers=${WEB_CONCURRENCY:-4}, port=${PORT:-8000})..."
exec gunicorn vectorbase.wsgi:application \
    --workers "${WEB_CONCURRENCY:-4}" \
    --bind "0.0.0.0:${PORT:-8000}" \
    --access-logfile - \
    --error-logfile -
