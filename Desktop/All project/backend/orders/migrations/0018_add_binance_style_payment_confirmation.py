# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0017_add_payment_deadline_to_p2p_transaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='buyer_marked_paid',
            field=models.BooleanField(default=False, help_text='Buyer has marked payment as complete'),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='buyer_marked_paid_at',
            field=models.DateTimeField(blank=True, help_text='When buyer marked payment as complete', null=True),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='payment_screenshot',
            field=models.ImageField(blank=True, help_text='Screenshot of payment proof uploaded by buyer', null=True, upload_to='p2p_payment_screenshots/'),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='seller_confirmed_payment',
            field=models.BooleanField(default=False, help_text='Seller has confirmed payment receipt'),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='seller_confirmed_payment_at',
            field=models.DateTimeField(blank=True, help_text='When seller confirmed payment', null=True),
        ),
    ]

