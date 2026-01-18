from django.core.management.base import BaseCommand
from analytics.models import Settings


class Command(BaseCommand):
    help = 'Clean up duplicate Settings records, keeping only one (pk=1)'

    def handle(self, *args, **options):
        count = Settings.objects.count()
        self.stdout.write(f'Found {count} Settings record(s)')
        
        if count == 0:
            # Create the singleton
            settings = Settings.objects.create(pk=1)
            self.stdout.write(self.style.SUCCESS(f'Created Settings record with pk=1'))
            return
        
        if count == 1:
            settings = Settings.objects.first()
            if settings.pk != 1:
                # Move existing to pk=1
                settings.pk = 1
                settings.save()
                self.stdout.write(self.style.SUCCESS(f'Moved Settings record to pk=1'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Settings record already at pk=1'))
            return
        
        # Multiple records - consolidate
        primary = Settings.objects.filter(pk=1).first()
        
        if primary:
            # Keep pk=1, delete others
            deleted_count = Settings.objects.exclude(pk=1).count()
            Settings.objects.exclude(pk=1).delete()
            self.stdout.write(self.style.SUCCESS(f'Removed {deleted_count} duplicate record(s), kept pk=1'))
        else:
            # No pk=1, use first and consolidate
            first = Settings.objects.first()
            Settings.objects.exclude(pk=first.pk).delete()
            first.pk = 1
            first.save()
            self.stdout.write(self.style.SUCCESS(f'Consolidated to single record with pk=1'))
        
        # Verify
        final_count = Settings.objects.count()
        if final_count == 1 and Settings.objects.filter(pk=1).exists():
            self.stdout.write(self.style.SUCCESS(f'Settings singleton verified: {final_count} record at pk=1'))
        else:
            self.stdout.write(self.style.ERROR(f'Warning: Still have {final_count} record(s)'))

