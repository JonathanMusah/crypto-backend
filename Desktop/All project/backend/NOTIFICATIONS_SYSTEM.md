# Notifications System Documentation

## Overview
Complete notification system with automatic creation via Django signals, REST API endpoints, and preparation for real-time WebSocket integration using Django Channels.

## Features

### Automatic Notification Creation
Notifications are automatically created when:
- ✅ **Transaction Approved**: When a crypto transaction status changes to 'approved'
- ✅ **Transaction Rejected**: When a crypto transaction status changes to 'declined'
- ✅ **Gift Card Order Created**: When a new gift card order is created
- ✅ **Gift Card Order Approved**: When gift card order status changes to 'approved'
- ✅ **Gift Card Order Declined**: When gift card order status changes to 'declined'
- ✅ **Gift Card Order Completed**: When gift card order status changes to 'completed'

### Notification Model
- `user`: ForeignKey to User
- `message`: Text content of notification
- `read`: Boolean flag (default: False)
- `notification_type`: Type of notification
- `title`: Notification title
- `related_object_type`: Optional type of related object
- `related_object_id`: Optional ID of related object
- `created_at`: Timestamp

## API Endpoints

### List Notifications
- **URL**: `/api/notifications/notifications/`
- **Method**: GET
- **Auth**: Required
- **Query Parameters**:
  - `notification_type`: Filter by type
  - `read`: Filter by read status (true/false)
  - `ordering`: Order by field (e.g., `-created_at`)
- **Response**: List of user's notifications

### Get Notification
- **URL**: `/api/notifications/notifications/{id}/`
- **Method**: GET
- **Auth**: Required

### Mark Notification as Read
- **URL**: `/api/notifications/notifications/{id}/mark_read/`
- **Method**: POST
- **Auth**: Required
- **Response**: Updated notification

### Mark All as Read
- **URL**: `/api/notifications/notifications/mark_all_read/`
- **Method**: POST
- **Auth**: Required
- **Response**: Count of updated notifications

### Get Unread Count
- **URL**: `/api/notifications/notifications/unread_count/`
- **Method**: GET
- **Auth**: Required
- **Response**: `{ "unread_count": 5 }`

## Notification Types

```python
NOTIFICATION_TYPE_CHOICES = [
    ('TRANSACTION_APPROVED', 'Transaction Approved'),
    ('TRANSACTION_REJECTED', 'Transaction Rejected'),
    ('GIFT_CARD_ORDER_CREATED', 'Gift Card Order Created'),
    ('GIFT_CARD_ORDER_APPROVED', 'Gift Card Order Approved'),
    ('GIFT_CARD_ORDER_DECLINED', 'Gift Card Order Declined'),
    ('GIFT_CARD_ORDER_COMPLETED', 'Gift Card Order Completed'),
    ('GIFT_CARD_PROOF_UPLOADED', 'Gift Card Proof Uploaded'),
    ('ORDER_COMPLETED', 'Order Completed'),
    ('ORDER_CANCELLED', 'Order Cancelled'),
    ('DEPOSIT_RECEIVED', 'Deposit Received'),
    ('WITHDRAWAL_COMPLETED', 'Withdrawal Completed'),
    ('KYC_APPROVED', 'KYC Approved'),
    ('KYC_REJECTED', 'KYC Rejected'),
    ('SYSTEM', 'System Notification'),
]
```

## Django Signals

The system uses Django signals to automatically create notifications:

1. **CryptoTransaction signals**: Track status changes
2. **GiftCardOrder signals**: Track creation and status changes
3. **Order signals**: Track completion and cancellation

Signals are automatically connected when the notifications app is loaded.

## Real-Time Integration (Django Channels)

The system is prepared for real-time WebSocket notifications using Django Channels.

### Files Created:
- `consumers.py`: WebSocket consumer for notifications
- `routing.py`: WebSocket URL routing
- `utils.py`: Helper functions with WebSocket support

### To Enable Real-Time Notifications:

1. **Install dependencies**:
```bash
pip install channels channels-redis
```

2. **Update settings.py**:
```python
INSTALLED_APPS = [
    # ... existing apps
    'channels',
]

ASGI_APPLICATION = 'config.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

3. **Update config/asgi.py** to include WebSocket routing

4. **Run with ASGI server**:
```bash
daphne config.asgi:application
# or
uvicorn config.asgi:application
```

### WebSocket Connection
- **URL**: `ws://localhost:8000/ws/notifications/`
- **Authentication**: JWT token in connection headers
- **Channel**: Each user connects to `notifications_{user_id}`

## Usage Examples

### Creating a Notification Manually
```python
from notifications.utils import create_notification

create_notification(
    user=request.user,
    notification_type='SYSTEM',
    title='Welcome!',
    message='Welcome to the platform!',
    related_object_type='user',
    related_object_id=user.id,
)
```

### Querying Notifications
```python
from notifications.models import Notification

# Get unread notifications
unread = Notification.objects.filter(user=user, read=False)

# Get notifications by type
transactions = Notification.objects.filter(
    user=user,
    notification_type='TRANSACTION_APPROVED'
)
```

## Database Indexes

The notification model includes optimized indexes for:
- User + Read status + Created date (for filtering unread)
- User + Created date (for listing)

## Future Enhancements

- Email notifications
- Push notifications (mobile)
- Notification preferences per user
- Notification grouping
- Rich notification content (images, actions)

