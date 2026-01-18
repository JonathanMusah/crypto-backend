#!/bin/bash

echo "Starting application..."
python manage.py migrate --no-input --run-syncdb
python manage.py collectstatic --no-input
gunicorn --bind 0.0.0.0:$PORT --workers 1 config.wsgi:application
