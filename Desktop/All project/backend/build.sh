#!/bin/bash
set -o errexit

pip install -r requirements.txt
python manage.py migrate --no-input || true
python manage.py collectstatic --no-input || true
