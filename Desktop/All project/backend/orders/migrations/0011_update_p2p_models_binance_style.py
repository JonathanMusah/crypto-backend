# Generated migration for Binance-style P2P service listings
# This migration updates P2P models to support seller-set rates and payment methods

from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


def migrate_listing_data(apps, schema_editor):
    """Migrate existing listing data to new structure"""
    P2PServiceListing = apps.get_model('orders', 'P2PServiceListing')
    
    for listing in P2PServiceListing.objects.all():
        # Migrate service_email to service-specific fields
        if hasattr(listing, 'service_email') and listing.service_email:
            if listing.service_type == 'paypal':
                listing.paypal_email = listing.service_email
            elif listing.service_type == 'cashapp':
                listing.cashapp_tag = listing.service_email  # May need adjustment
            elif listing.service_type == 'zelle':
                listing.zelle_email = listing.service_email
        
        # Migrate service_amount to available_amount_usd
        if hasattr(listing, 'service_amount'):
            listing.available_amount_usd = listing.service_amount
        
        # Calculate rate from asking_price_cedis / service_amount
        if hasattr(listing, 'asking_price_cedis') and hasattr(listing, 'service_amount'):
            if listing.service_amount and listing.service_amount > 0:
                listing.rate_cedis_per_usd = listing.asking_price_cedis / listing.service_amount
            else:
                listing.rate_cedis_per_usd = Decimal('12.00')  # Default rate
        else:
            listing.rate_cedis_per_usd = Decimal('12.00')  # Default rate
        
        # Set default payment method (MoMo)
        if not listing.accepted_payment_methods:
            listing.accepted_payment_methods = [{'method': 'momo', 'provider': 'MTN', 'number': '', 'name': ''}]
        
        listing.save()


def migrate_transaction_data(apps, schema_editor):
    """Migrate existing transaction data to new structure"""
    P2PServiceTransaction = apps.get_model('orders', 'P2PServiceTransaction')
    
    for transaction in P2PServiceTransaction.objects.all():
        # Calculate amount_usd from agreed_price_cedis and listing rate
        if transaction.listing and hasattr(transaction.listing, 'rate_cedis_per_usd'):
            if transaction.listing.rate_cedis_per_usd and transaction.listing.rate_cedis_per_usd > 0:
                transaction.amount_usd = transaction.agreed_price_cedis / transaction.listing.rate_cedis_per_usd
            else:
                # Fallback: assume rate of 12
                transaction.amount_usd = transaction.agreed_price_cedis / Decimal('12.00')
        else:
            # Fallback: assume rate of 12
            transaction.amount_usd = transaction.agreed_price_cedis / Decimal('12.00')
        
        # Migrate service_email to service_identifier
        if hasattr(transaction, 'service_email') and transaction.service_email:
            transaction.service_identifier = transaction.service_email
        
        # Set default payment method
        if not transaction.selected_payment_method:
            transaction.selected_payment_method = 'momo'
        
        transaction.save()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_add_p2p_models"),
    ]

    operations = [
        # P2PServiceListing changes
        # Add new fields first
        migrations.AddField(
            model_name='p2pservicelisting',
            name='paypal_email',
            field=models.EmailField(blank=True, null=True, help_text='PayPal email address (for PayPal listings)'),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='cashapp_tag',
            field=models.CharField(blank=True, max_length=100, null=True, help_text='CashApp tag starting with $ (for CashApp listings)'),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='zelle_email',
            field=models.EmailField(blank=True, null=True, help_text='Zelle email address (for Zelle listings)'),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='min_amount_usd',
            field=models.DecimalField(decimal_places=2, default=Decimal('1.00'), max_digits=10, help_text='Minimum transaction amount in USD'),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='max_amount_usd',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, help_text='Maximum transaction amount in USD (null = unlimited)'),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='available_amount_usd',
            field=models.DecimalField(decimal_places=2, default=Decimal('100.00'), max_digits=10, help_text='Total amount available in USD'),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='rate_cedis_per_usd',
            field=models.DecimalField(decimal_places=4, default=Decimal('12.0000'), max_digits=10, help_text="Seller's rate: 1 USD = X GHS"),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='accepted_payment_methods',
            field=models.JSONField(default=list, help_text="List of payment methods seller accepts with details. Format: [{'method': 'momo', 'provider': 'MTN', 'number': '0244123456', 'name': 'John Doe'}, {'method': 'bank', 'bank_name': 'GCB', 'account_number': '1234567890', 'account_name': 'John Doe'}]"),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='terms_notes',
            field=models.TextField(blank=True, help_text="Seller's terms, notes, or special instructions"),
        ),
        migrations.AddField(
            model_name='p2pservicelisting',
            name='service_identifier_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64, help_text='SHA256 hash of service identifier (email/tag) for duplicate detection'),
        ),
        
        # Migrate existing data
        migrations.RunPython(migrate_listing_data, reverse_code=migrations.RunPython.noop),
        
        # Remove old fields (after data migration)
        migrations.RemoveField(
            model_name='p2pservicelisting',
            name='service_email',
        ),
        migrations.RemoveField(
            model_name='p2pservicelisting',
            name='service_amount',
        ),
        migrations.RemoveField(
            model_name='p2pservicelisting',
            name='asking_price_cedis',
        ),
        migrations.RemoveField(
            model_name='p2pservicelisting',
            name='service_email_hash',
        ),
        
        # P2PServiceTransaction changes
        # Add new fields first
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='amount_usd',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, help_text='Transaction amount in USD'),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='selected_payment_method',
            field=models.CharField(blank=True, max_length=20, help_text="Payment method buyer selected (momo, bank, other)"),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='payment_method_details',
            field=models.JSONField(blank=True, default=dict, help_text="Details for selected payment method (provider, number, account, etc.)"),
        ),
        migrations.AddField(
            model_name='p2pservicetransaction',
            name='service_identifier',
            field=models.CharField(blank=True, max_length=255, help_text="Service identifier provided by seller (email or tag based on service type)"),
        ),
        
        # Migrate existing transaction data
        migrations.RunPython(migrate_transaction_data, reverse_code=migrations.RunPython.noop),
        
        # Remove old field (after data migration)
        migrations.RemoveField(
            model_name='p2pservicetransaction',
            name='service_email',
        ),
        
        # Update indexes
        migrations.AlterIndexTogether(
            name='p2pservicelisting',
            index_together=set(),
        ),
        migrations.AddIndex(
            model_name='p2pservicelisting',
            index=models.Index(fields=['service_type', 'status'], name='orders_p2ps_service_type_status_idx'),
        ),
        migrations.AddIndex(
            model_name='p2pservicelisting',
            index=models.Index(fields=['seller', 'status'], name='orders_p2ps_seller_status_idx'),
        ),
        migrations.AddIndex(
            model_name='p2pservicelisting',
            index=models.Index(fields=['service_identifier_hash'], name='orders_p2ps_service_identifier_hash_idx'),
        ),
    ]
