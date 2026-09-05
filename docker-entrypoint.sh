#!/bin/sh
set -eu

python manage.py collectstatic --noinput
exec gunicorn helixhealth.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --access-logfile - \
  --error-logfile -
