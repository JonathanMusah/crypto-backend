# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_add_binance_style_payment_confirmation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='p2pservicetransaction',
            name='status',
            field=models.CharField(choices=[('pending_payment', 'Pending Payment'), ('payment_received', 'Payment Received (Escrow)'), ('buyer_marked_paid', 'Buyer Marked as Paid'), ('seller_confirmed_payment', 'Seller Confirmed Payment'), ('service_provided', 'Service Details Provided by Seller'), ('verifying', 'Buyer Verifying'), ('completed', 'Completed'), ('disputed', 'Disputed'), ('cancelled', 'Cancelled'), ('refunded', 'Refunded')], default='pending_payment', max_length=30),
        ),
    ]

