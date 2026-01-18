# Database Migration Guide

## Prerequisites

1. Python 3.8+ installed
2. PostgreSQL installed and running
3. Virtual environment (recommended)

## Setup Instructions

### 1. Create and Activate Virtual Environment

**Windows:**
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
```

**Linux/Mac:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `backend` directory with the following content:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_NAME=crypto_platform
DB_USER=postgres
DB_PASSWORD=your-postgres-password
DB_HOST=localhost
DB_PORT=5432

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Celery Settings
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 4. Create PostgreSQL Database

Connect to PostgreSQL and create the database:

```sql
CREATE DATABASE crypto_platform;
```

Or using psql command:
```bash
psql -U postgres
CREATE DATABASE crypto_platform;
\q
```

### 5. Run Migrations

```bash
# Create migration files
python manage.py makemigrations

# Apply migrations to database
python manage.py migrate
```

Expected output should show migrations for:
- authentication (User model)
- wallets (Wallet, CryptoTransaction)
- orders (GiftCard, GiftCardOrder, Order, Trade)
- tutorials (Tutorial, TutorialProgress)
- notifications (Notification)
- analytics (Settings, AnalyticsEvent, UserMetric)
- kyc (KYCVerification)

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account.

### 7. Run Development Server

```bash
python manage.py runserver
```

The server will start at: http://localhost:8000

### 8. Access Admin Panel

Navigate to: http://localhost:8000/admin/

Login with the superuser credentials created in step 6.

## Verification Steps

### 1. Check Database Tables

Connect to PostgreSQL and verify tables were created:

```sql
\c crypto_platform
\dt
```

You should see the following tables:
- users
- wallets
- crypto_transactions
- gift_cards
- gift_card_orders
- orders
- trades
- tutorials
- tutorial_progress
- notifications
- settings
- analytics_events
- user_metrics
- kyc_verifications

### 2. Test API Endpoints

Visit the browsable API:
- http://localhost:8000/api/wallets/wallets/
- http://localhost:8000/api/wallets/crypto-transactions/
- http://localhost:8000/api/orders/giftcards/
- http://localhost:8000/api/orders/giftcard-orders/
- http://localhost:8000/api/tutorials/
- http://localhost:8000/api/notifications/
- http://localhost:8000/api/analytics/settings/

### 3. Test Admin Interface

Access Django Admin:
- http://localhost:8000/admin/

You should see all models listed under their respective apps.

## Troubleshooting

### Migration Conflicts

If you encounter migration conflicts:

```bash
# Reset migrations (WARNING: This will delete data)
python manage.py migrate --fake <app_name> zero
python manage.py migrate <app_name>
```

### Database Connection Issues

1. Verify PostgreSQL is running:
   ```bash
   # Windows
   pg_ctl status
   
   # Linux
   sudo service postgresql status
   ```

2. Check database credentials in `.env` file
3. Ensure database exists:
   ```bash
   psql -U postgres -l
   ```

### Missing Dependencies

If you get import errors:

```bash
pip install --upgrade -r requirements.txt
```

## Docker Alternative

If you prefer using Docker:

```bash
# From project root
docker-compose up -d

# Run migrations in container
docker-compose exec backend python manage.py migrate

# Create superuser in container
docker-compose exec backend python manage.py createsuperuser
```

## Sample Data (Optional)

To create sample data for testing, you can use Django shell:

```bash
python manage.py shell
```

Then run:

```python
from authentication.models import User
from wallets.models import Wallet
from orders.models import GiftCard

# Create a test user
user = User.objects.create_user(
    username='testuser',
    email='test@example.com',
    password='testpass123',
    role='user',
    kyc_status='pending'
)

# Create wallet for user
wallet = Wallet.objects.create(
    user=user,
    balance_cedis=0,
    balance_crypto=0,
    escrow_balance=0
)

# Create sample gift card
giftcard = GiftCard.objects.create(
    name='$100 Amazon Gift Card',
    brand='Amazon',
    rate_buy=450.00,
    rate_sell=420.00,
    is_active=True
)

print("Sample data created successfully!")
```

## Next Steps

After successful migration:

1. Configure email settings for notifications
2. Set up Celery for background tasks
3. Configure Redis for caching
4. Set up payment gateway integrations
5. Configure file storage for images
6. Set up monitoring and logging

## Support

If you encounter issues:
1. Check Django logs
2. Verify PostgreSQL connection
3. Ensure all dependencies are installed
4. Check environment variables
