from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Make a user an admin by email'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email of the user to make admin')
        parser.add_argument(
            '--password',
            type=str,
            help='Optional: Set a new password for the user',
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options.get('password')

        try:
            user = User.objects.get(email=email)
            
            # Update user to admin
            user.role = 'admin'
            user.is_staff = True
            user.is_superuser = True
            
            if password:
                user.set_password(password)
                self.stdout.write(
                    self.style.SUCCESS(f'Password updated for {email}')
                )
            
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully made {email} an admin user!\n'
                    f'Role: {user.role}\n'
                    f'Is Staff: {user.is_staff}\n'
                    f'Is Superuser: {user.is_superuser}'
                )
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User with email {email} does not exist')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )

