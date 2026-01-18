from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from orders.models import GiftCard
from rates.models import CryptoRate
from tutorials.models import Tutorial
from analytics.models import Settings
from wallets.models import Wallet, WalletTransaction, CryptoTransaction
from marketing.models import (
    FeatureBlock,
    PolicyPage,
    SecurityHighlight,
    SupportedAsset,
    Testimonial,
)
import random
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with sample data for all models'

    def handle(self, *args, **options):
        self.stdout.write('Populating sample data...')
        
        # Create admin user
        self.create_admin_user()
        
        # Create sample users and wallets
        self.create_sample_users()
        
        # Create gift cards
        self.create_gift_cards()
        
        # Create crypto rates
        self.create_crypto_rates()
        
        # Create tutorials (if not already populated)
        self.create_tutorials()
        
        # Create system settings
        self.create_system_settings()

        # Create wallet transactions and crypto trades
        self.create_wallet_data()

        # Marketing content
        self.create_marketing_content()
        self.create_policy_pages()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully populated sample data!')
        )

    def create_admin_user(self):
        admin_user, created = User.objects.get_or_create(
            email='admin@gmail.com',
            defaults={
                'username': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'role': 'admin'
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS('Created admin user: admin@gmail.com')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Admin user already exists')
            )

    def create_sample_users(self):
        sample_users = [
            {
                'email': 'user1@example.com',
                'username': 'user1',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '+233123456789'
            },
            {
                'email': 'user2@example.com',
                'username': 'user2',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'phone': '+233987654321'
            }
        ]
        
        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults=user_data
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Created user: {user.email}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'User already exists: {user.email}')
                )

            wallet_defaults = {
                'balance_cedis': Decimal(random.randrange(5000, 20000)),
                'balance_crypto': Decimal('0.25340000'),
                'escrow_balance': Decimal(random.randrange(500, 5000)),
            }
            Wallet.objects.get_or_create(user=user, defaults=wallet_defaults)

    def create_gift_cards(self):
        gift_cards_data = [
            {
                'name': 'Amazon Gift Card',
                'brand': 'Amazon',
                'rate_buy': Decimal('0.95'),
                'rate_sell': Decimal('0.90'),
                'is_active': True
            },
            {
                'name': 'Google Play',
                'brand': 'Google',
                'rate_buy': Decimal('0.98'),
                'rate_sell': Decimal('0.93'),
                'is_active': True
            },
            {
                'name': 'Apple iTunes',
                'brand': 'Apple',
                'rate_buy': Decimal('0.97'),
                'rate_sell': Decimal('0.92'),
                'is_active': True
            },
            {
                'name': 'Steam Wallet',
                'brand': 'Steam',
                'rate_buy': Decimal('0.96'),
                'rate_sell': Decimal('0.91'),
                'is_active': True
            },
            {
                'name': 'Netflix Gift Card',
                'brand': 'Netflix',
                'rate_buy': Decimal('0.94'),
                'rate_sell': Decimal('0.89'),
                'is_active': True
            }
        ]
        
        created_count = 0
        for card_data in gift_cards_data:
            card, created = GiftCard.objects.get_or_create(
                name=card_data['name'],
                defaults=card_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created gift card: {card.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Gift card already exists: {card.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} new gift cards')
        )

    def create_crypto_rates(self):
        crypto_rates_data = [
            {
                'crypto_id': 'bitcoin',
                'symbol': 'BTC',
                'usd_price': Decimal('35000.00'),
                'cedis_price': Decimal('350000.00'),
                'usd_to_cedis_rate': Decimal('10.00')
            },
            {
                'crypto_id': 'ethereum',
                'symbol': 'ETH',
                'usd_price': Decimal('2500.00'),
                'cedis_price': Decimal('25000.00'),
                'usd_to_cedis_rate': Decimal('10.00')
            },
            {
                'crypto_id': 'binancecoin',
                'symbol': 'BNB',
                'usd_price': Decimal('300.00'),
                'cedis_price': Decimal('3000.00'),
                'usd_to_cedis_rate': Decimal('10.00')
            }
        ]
        
        created_count = 0
        for rate_data in crypto_rates_data:
            rate, created = CryptoRate.objects.get_or_create(
                crypto_id=rate_data['crypto_id'],
                is_active=True,
                defaults=rate_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created crypto rate: {rate.symbol}')
                )
            else:
                # Update existing rate
                CryptoRate.objects.filter(crypto_id=rate_data['crypto_id'], is_active=True).update(**rate_data)
                self.stdout.write(
                    self.style.WARNING(f'Updated crypto rate: {rate.symbol}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created/updated {created_count} crypto rates')
        )

    def create_tutorials(self):
        # Check if tutorials already exist
        if Tutorial.objects.count() > 0:
            self.stdout.write(
                self.style.WARNING('Tutorials already exist, skipping...')
            )
            return
            
        # Use the existing populate_tutorials command logic
        from tutorials.management.commands.populate_tutorials import Command as TutorialCommand
        tutorial_command = TutorialCommand()
        tutorial_command.stdout = self.stdout
        tutorial_command.style = self.style
        tutorial_command.handle(*args, **options)

    def create_system_settings(self):
        settings, created = Settings.objects.get_or_create(
            id=1,
            defaults={
                'live_rate_source': 'coinmarketcap',
                'escrow_percent': Decimal('2.00'),
                'support_contacts': {
                    'email': 'support@cryptoplatform.com',
                    'phone': '+233 123 456 789'
                }
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created system settings')
            )
        else:
            self.stdout.write(
                self.style.WARNING('System settings already exist')
            )

    def create_wallet_data(self):
        """Seed wallet transactions and crypto trades for demo users."""
        for wallet in Wallet.objects.all():
            if not wallet.transactions.exists():
                base_balance = wallet.balance_cedis or Decimal('10000')
                samples = [
                    ('deposit', Decimal('3000.00'), 'cedis', 'Salary deposit'),
                    ('escrow_lock', Decimal('1500.00'), 'cedis', 'Trade escrow reserve'),
                    ('crypto_buy', Decimal('2500.00'), 'cedis', 'BTC purchase order'),
                    ('escrow_release', Decimal('1500.00'), 'cedis', 'Order approved'),
                ]
                for index, (txn_type, amount, currency, description) in enumerate(samples):
                    before = base_balance + Decimal(index * 250)
                    after = before + (amount if txn_type in ['deposit', 'escrow_release'] else -amount)
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type=txn_type,
                        amount=amount,
                        currency=currency,
                        status='completed',
                        reference=WalletTransaction.generate_reference(),
                        description=description,
                        balance_before=before,
                        balance_after=after,
                    )

            if not wallet.user.crypto_transactions.exists():
                trade_samples = [
                    {
                        'type': 'buy',
                        'cedis_amount': Decimal('1800.00'),
                        'crypto_amount': Decimal('0.0045'),
                        'rate': Decimal('400000.00'),
                        'payment_method': 'momo',
                        'status': 'approved',
                    },
                    {
                        'type': 'sell',
                        'cedis_amount': Decimal('950.00'),
                        'crypto_amount': Decimal('0.0021'),
                        'rate': Decimal('452000.00'),
                        'payment_method': 'bank',
                        'status': 'pending',
                    },
                ]
                for sample in trade_samples:
                    CryptoTransaction.objects.create(
                        user=wallet.user,
                        type=sample['type'],
                        cedis_amount=sample['cedis_amount'],
                        crypto_amount=sample['crypto_amount'],
                        rate=sample['rate'],
                        status=sample['status'],
                        payment_method=sample['payment_method'],
                        reference=CryptoTransaction.generate_reference(),
                    )

    def create_marketing_content(self):
        if not FeatureBlock.objects.exists():
            FeatureBlock.objects.bulk_create([
                FeatureBlock(
                    title='Unified trading workspace',
                    subtitle='Glassmorphic OS',
                    description='Monitor fiat, crypto and escrow health within a single adaptive grid.',
                    icon='Layout',
                    accent_color='#38bdf8',
                    order=0,
                ),
                FeatureBlock(
                    title='Bank-grade safeguards',
                    subtitle='SOC2-ready controls',
                    description='Hardware-backed MFA, device fingerprinting and ledger snapshots ship by default.',
                    icon='ShieldCheck',
                    accent_color='#a855f7',
                    order=1,
                ),
                FeatureBlock(
                    title='Ghana-first liquidity',
                    subtitle='Momo + Bank rails',
                    description='Instant cedi settlement across MTN, Vodafone Cash and partner banks.',
                    icon='Wallet',
                    accent_color='#f97316',
                    order=2,
                ),
            ])

        if not SecurityHighlight.objects.exists():
            SecurityHighlight.objects.bulk_create([
                SecurityHighlight(
                    title='Real-time device attestation',
                    description='Every session is bound to a signed device profile for zero-trust trading.',
                    badge='Live',
                    icon='Fingerprint',
                    status='Monitored 24/7',
                    order=0,
                ),
                SecurityHighlight(
                    title='Escrow automation',
                    description='Trades automatically lock and release funds once KYC checks clear.',
                    badge='Automation',
                    icon='Lock',
                    status='Policy v2.1',
                    order=1,
                ),
                SecurityHighlight(
                    title='Ledger reconciliation',
                    description='Hourly proofs keep fiat + crypto ledgers balanced with SHA256 audit logs.',
                    badge='Verified',
                    icon='BarChart',
                    status='No drift detected',
                    order=2,
                ),
            ])

        if not SupportedAsset.objects.exists():
            asset_data = [
                ('Bitcoin', 'BTC', 'Lightning', 'store of value', 1),
                ('Ethereum', 'ETH', 'Mainnet', 'Defi', 2),
                ('Solana', 'SOL', 'Solana', 'Payments', 3),
                ('Tether', 'USDT', 'Tron', 'Stablecoin', 4),
                ('BNB', 'BNB', 'BNB Chain', 'Exchange', 5),
                ('Cardano', 'ADA', 'Cardano', 'Layer1', 6),
                ('Polygon', 'MATIC', 'Polygon', 'Scaling', 7),
                ('Ripple', 'XRP', 'XRPL', 'Payments', 8),
            ]
            SupportedAsset.objects.bulk_create([
                SupportedAsset(
                    name=name,
                    symbol=symbol,
                    network=network,
                    segment=segment,
                    liquidity_rank=rank,
                    description=f'{name} ready for cedi pairs.',
                    order=rank,
                )
                for (name, symbol, network, segment, rank) in asset_data
            ])

        if not Testimonial.objects.exists():
            Testimonial.objects.bulk_create([
                Testimonial(
                    author_name='Ama Boateng',
                    role='Treasury Lead',
                    company='AccraPay',
                    quote='CryptoGhana replaced three internal dashboards with one glass workspace. Reconciliations that took an afternoon now finish before lunch.',
                    rating=4.9,
                    highlight='Cut ops time by 60%',
                    avatar_url='https://i.pravatar.cc/160?img=32',
                    order=0,
                ),
                Testimonial(
                    author_name='Kwesi Mensah',
                    role='Founder',
                    company='Volt Exchange',
                    quote='The dark mode redesign is the first interface our night desk actually compliments. Execution speed plus clarity keeps us loyal.',
                    rating=5.0,
                    highlight='Preferred pro desk',
                    avatar_url='https://i.pravatar.cc/160?img=12',
                    order=1,
                ),
                Testimonial(
                    author_name='Linda Owusu',
                    role='Compliance Lead',
                    company='Axis Mobile',
                    quote='Policy controls, audit trails and KYC nudges are all editable from admin. The content team updates copy without dev cycles.',
                    rating=4.8,
                    highlight='Admin editable content',
                    avatar_url='https://i.pravatar.cc/160?img=48',
                    order=2,
                ),
            ])

    def create_policy_pages(self):
        today = timezone.now().date()
        policies = {
            'privacy': {
                'title': 'Privacy Policy',
                'summary': 'How CryptoGhana collects, processes and protects customer information across wallets, trading, and admin tools.',
                'hero_badge': 'Updated weekly',
            },
            'terms': {
                'title': 'Terms of Service',
                'summary': 'The rules of engagement for trading digital assets, paying out merchants, and using our dashboards.',
                'hero_badge': 'Governing agreement',
            },
            'compliance': {
                'title': 'Compliance Standards',
                'summary': 'Detailed overview of the safeguards, KYC tiers, and AML controls we enforce for all users.',
                'hero_badge': 'SOC2-ready',
            },
        }

        default_sections = [
            {
                'title': 'Data collection & purpose',
                'body': 'We collect profile, KYC artifacts, transaction metadata, and telemetry strictly to operate the platform and comply with regulators.',
            },
            {
                'title': 'Retention & deletion',
                'body': 'Sensitive records live in encrypted storage with lifecycle policies. Export or deletion requests are handled through support safely.',
            },
            {
                'title': 'Contact',
                'body': 'Reach compliance@cryptoghana.com for clarifications and DPA requests.',
            },
        ]

        for slug, payload in policies.items():
            PolicyPage.objects.update_or_create(
                slug=slug,
                defaults={
                    'title': payload['title'],
                    'summary': payload['summary'],
                    'sections': [section.copy() for section in default_sections],
                    'last_updated': today,
                    'hero_badge': payload['hero_badge'],
                },
            )