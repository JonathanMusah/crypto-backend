"""
WSGI config for crypto platform project.
"""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Run migrations automatically on app startup (for free tier Render deployment)
# This ensures database is initialized before any requests are processed
def run_migrations():
    """Run Django migrations on app startup."""
    try:
        from django.core.management import call_command
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        
        # Check if we're running on Render (by checking for Render environment)
        if os.getenv('RENDER') == 'true':
            print("=== Running Database Migrations ===", file=sys.stderr)
            try:
                # Test database connection
                with connection.cursor() as cursor:
                    pass
                # Run migrations
                call_command('migrate', verbosity=2, interactive=False)
                print("=== Migrations Complete ===", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Migration failed: {e}", file=sys.stderr)
                print("Continuing app startup...", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not run migrations: {e}", file=sys.stderr)

# Run migrations before getting WSGI application
run_migrations()

application = get_wsgi_application()

