#!/bin/bash
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running migrations..."
python manage.py migrate --no-input || echo "Migration failed, continuing..."

echo "Collecting static files..."
python manage.py collectstatic --no-input || echo "Collectstatic failed, continuing..."

echo "Build complete!"
