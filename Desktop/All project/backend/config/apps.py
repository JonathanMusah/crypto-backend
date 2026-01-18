"""
Django App Configuration
"""
from django.apps import AppConfig


class ConfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config'

    def ready(self):
        """Enable SQLite WAL mode for better concurrency when Django is ready"""
        from django.db import connection
        
        if connection.vendor == 'sqlite':
            try:
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA journal_mode=WAL;')
                    result = cursor.fetchone()
                    if result and result[0] == 'wal':
                        print('✓ SQLite WAL mode enabled for better concurrency')
            except Exception as e:
                print(f'⚠ Warning: Could not enable SQLite WAL mode: {e}')

