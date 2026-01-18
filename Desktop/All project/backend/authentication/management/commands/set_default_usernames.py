"""
Management command to set default usernames for existing users.
Generates usernames from email if username is empty or defaults to 'user_{id}'.
"""
from django.core.management.base import BaseCommand
from authentication.models import User
import re


class Command(BaseCommand):
    help = 'Set default usernames for users who don\'t have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without saving changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        users_updated = 0
        users_skipped = 0
        
        self.stdout.write(self.style.SUCCESS('Starting username assignment...'))
        
        for user in User.objects.all():
            # Check if user already has a valid username
            if user.username and user.username.strip():
                # Check if username is just the email prefix (we'll still update it for consistency)
                email_prefix = user.email.split('@')[0] if user.email else None
                if user.username == email_prefix:
                    users_skipped += 1
                    continue
            
            # Generate username from email
            if user.email:
                base_username = user.email.split('@')[0]
                # Clean username - only alphanumeric, dots, underscores, hyphens
                base_username = re.sub(r'[^a-zA-Z0-9._-]', '', base_username)
                # Remove leading/trailing dots, underscores, hyphens
                base_username = base_username.strip('._-')
                
                # If base_username is empty after cleaning, use 'user' prefix
                if not base_username:
                    base_username = 'user'
                
                # Check if username already exists
                username = base_username
                counter = 1
                while User.objects.exclude(pk=user.pk).filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
            else:
                # Fallback: use user_{id}
                username = f"user_{user.id}"
            
            if not dry_run:
                user.username = username
                user.save(update_fields=['username'])
                self.stdout.write(
                    self.style.SUCCESS(f'[OK] Set username for {user.email}: {username}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'[DRY RUN] Would set username for {user.email}: {username}')
                )
            
            users_updated += 1
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Would update {users_updated} users'))
            self.stdout.write(self.style.WARNING(f'Skipped {users_skipped} users (already have username)'))
        else:
            self.stdout.write(self.style.SUCCESS(f'[OK] Updated {users_updated} users'))
            self.stdout.write(self.style.SUCCESS(f'[OK] Skipped {users_skipped} users (already have username)'))

