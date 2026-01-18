"""
Management command to sync KYC verification status to User.kyc_status
This fixes any existing approved KYC records that weren't synced to User.kyc_status
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from kyc.models import KYCVerification

User = get_user_model()


class Command(BaseCommand):
    help = 'Sync KYC verification status to User.kyc_status for all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all KYC verifications
        verifications = KYCVerification.objects.select_related('user').all()
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        for verification in verifications:
            user = verification.user
            
            # Map KYCVerification status to User.kyc_status
            status_map = {
                'APPROVED': 'approved',
                'REJECTED': 'rejected',
                'PENDING': 'pending',
                'UNDER_REVIEW': 'pending',
            }
            
            expected_status = status_map.get(verification.status, 'pending')
            
            # Check if sync is needed
            if user.kyc_status != expected_status:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Would sync: {user.email} - "
                            f"KYCVerification.status={verification.status} -> "
                            f"User.kyc_status={expected_status} "
                            f"(currently: {user.kyc_status})"
                        )
                    )
                else:
                    try:
                        user.kyc_status = expected_status
                        user.save(update_fields=['kyc_status'])
                        synced_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Synced: {user.email} - "
                                f"KYCVerification.status={verification.status} -> "
                                f"User.kyc_status={expected_status}"
                            )
                        )
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"Error syncing {user.email}: {str(e)}"
                            )
                        )
            else:
                skipped_count += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN - Would sync: {synced_count} users"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Synced: {synced_count} users"))
        self.stdout.write(self.style.SUCCESS(f"Skipped (already synced): {skipped_count} users"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count} users"))
        self.stdout.write(self.style.SUCCESS('='*50))

