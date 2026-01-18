#!/bin/bash
set -e  # Exit on first error

echo "=== Starting Django Application ==="
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Django version: $(python -c 'import django; print(django.VERSION)')"

# Run migrations with verbose output
echo "=== Running Database Migrations ==="
python manage.py migrate --no-input --verbosity 2

# Collect static files
echo "=== Collecting Static Files ==="
python manage.py collectstatic --no-input --verbosity 1 || echo "Warning: Collectstatic had issues, continuing..."

# Start gunicorn
echo "=== Starting Gunicorn ==="
echo "Listening on 0.0.0.0:$PORT (PORT=$PORT)"
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 300 --access-logfile - config.wsgi:application
