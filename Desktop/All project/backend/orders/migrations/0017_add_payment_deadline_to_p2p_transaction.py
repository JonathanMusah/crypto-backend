# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0016_add_escrow_release_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='payment_deadline',
            field=models.DateTimeField(blank=True, help_text='Deadline for buyer to complete payment (15 minutes)', null=True),
        ),
    ]

