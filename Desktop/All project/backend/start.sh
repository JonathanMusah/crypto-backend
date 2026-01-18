#!/bin/bash
set -o errexit

echo "Starting application..."
echo "Running migrations again at startup..."
python manage.py migrate --no-input || echo "Startup migration check complete"

echo "Starting gunicorn..."
gunicorn --bind 0.0.0.0:$PORT --workers 1 config.wsgi:application
