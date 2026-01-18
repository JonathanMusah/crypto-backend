# API Endpoints Documentation

## Base URL
```
http://localhost:8000/api
```

## Authentication

All endpoints require JWT authentication except where noted.

### Headers
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## 1. Authentication Endpoints

### Register User
- **POST** `/api/auth/register/`
- **Public**: Yes
- **Body**:
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "SecurePass123",
  "password2": "SecurePass123",
  "phone": "+233123456789"
}
```

### Login
- **POST** `/api/auth/login/`
- **Public**: Yes
- **Body**:
```json
{
  "email": "john@example.com",
  "password": "SecurePass123"
}
```
- **Response**:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "email": "john@example.com",
    "role": "user",
    "kyc_status": "pending"
  }
}
```

---

## 2. Wallet Endpoints

### List All Wallets (Admin)
- **GET** `/api/wallets/wallets/`
- **Admin Only**: Yes
- **Response**:
```json
[
  {
    "id": 1,
    "user": 1,
    "balance_cedis": "5000.00",
    "balance_crypto": "0.15000000",
    "escrow_balance": "100.00",
    "updated_at": "2024-11-16T10:30:00Z"
  }
]
```

### Get My Wallet
- **GET** `/api/wallets/wallets/my_wallet/`
- **Response**:
```json
{
  "id": 1,
  "user": 1,
  "balance_cedis": "5000.00",
  "balance_crypto": "0.15000000",
  "escrow_balance": "100.00",
  "updated_at": "2024-11-16T10:30:00Z"
}
```

### Get Wallet Details
- **GET** `/api/wallets/wallets/{id}/`

### Update Wallet
- **PUT/PATCH** `/api/wallets/wallets/{id}/`
- **Admin Only**: Yes

---

## 3. Crypto Transaction Endpoints

### List Crypto Transactions
- **GET** `/api/wallets/crypto-transactions/`
- **Query Parameters**:
  - `type`: buy, sell
  - `status`: pending, approved, declined
  - `payment_method`: momo, bank, crypto
  - `search`: Search by reference
  - `ordering`: created_at, -created_at

### Create Crypto Transaction
- **POST** `/api/wallets/crypto-transactions/`
- **Body**:
```json
{
  "type": "buy",
  "cedis_amount": "1000.00",
  "crypto_amount": "0.025",
  "rate": "40000.00",
  "payment_method": "momo",
  "reference": "TXN-20241116-001"
}
```

### Get Transaction Details
- **GET** `/api/wallets/crypto-transactions/{id}/`

### Update Transaction
- **PUT/PATCH** `/api/wallets/crypto-transactions/{id}/`
- **Admin Only**: For status updates

---

## 4. Gift Card Endpoints

### List Gift Cards
- **GET** `/api/orders/giftcards/`
- **Public**: Yes (only active cards shown)
- **Query Parameters**:
  - `brand`: Filter by brand
  - `is_active`: true, false
  - `search`: Search by name or brand
  - `ordering`: brand, name, created_at

- **Response**:
```json
[
  {
    "id": 1,
    "name": "$100 Amazon Gift Card",
    "brand": "Amazon",
    "rate_buy": "450.00",
    "rate_sell": "420.00",
    "image": "http://localhost:8000/media/giftcards/amazon.jpg",
    "is_active": true,
    "created_at": "2024-11-16T10:00:00Z",
    "updated_at": "2024-11-16T10:00:00Z"
  }
]
```

### Create Gift Card
- **POST** `/api/orders/giftcards/`
- **Admin Only**: Yes
- **Body** (multipart/form-data):
```json
{
  "name": "$50 iTunes Gift Card",
  "brand": "iTunes",
  "rate_buy": "380.00",
  "rate_sell": "350.00",
  "image": "<file>",
  "is_active": true
}
```

### Get Gift Card Details
- **GET** `/api/orders/giftcards/{id}/`

### Update Gift Card
- **PUT/PATCH** `/api/orders/giftcards/{id}/`
- **Admin Only**: Yes

### Delete Gift Card
- **DELETE** `/api/orders/giftcards/{id}/`
- **Admin Only**: Yes

---

## 5. Gift Card Order Endpoints

### List Gift Card Orders
- **GET** `/api/orders/giftcard-orders/`
- **Query Parameters**:
  - `status`: pending, approved, declined, completed
  - `card`: Filter by gift card ID
  - `ordering`: created_at, -created_at

- **Response**:
```json
[
  {
    "id": 1,
    "user": 1,
    "user_email": "john@example.com",
    "card": 1,
    "card_name": "$100 Amazon Gift Card",
    "amount": "100.00",
    "status": "pending",
    "proof_image": "http://localhost:8000/media/giftcard_proofs/proof1.jpg",
    "created_at": "2024-11-16T11:00:00Z",
    "updated_at": "2024-11-16T11:00:00Z"
  }
]
```

### Create Gift Card Order
- **POST** `/api/orders/giftcard-orders/`
- **Body** (multipart/form-data):
```json
{
  "card": 1,
  "amount": "100.00",
  "proof_image": "<file>"
}
```

### Get Gift Card Order Details
- **GET** `/api/orders/giftcard-orders/{id}/`

### Update Gift Card Order
- **PUT/PATCH** `/api/orders/giftcard-orders/{id}/`

### Approve Gift Card Order
- **POST** `/api/orders/giftcard-orders/{id}/approve/`
- **Admin Only**: Yes
- **Response**:
```json
{
  "message": "Gift card order approved"
}
```

### Decline Gift Card Order
- **POST** `/api/orders/giftcard-orders/{id}/decline/`
- **Admin Only**: Yes
- **Response**:
```json
{
  "message": "Gift card order declined"
}
```

---

## 6. Tutorial Endpoints

### List Tutorials
- **GET** `/api/tutorials/`
- **Query Parameters**:
  - `category`: getting_started, trading, wallet, security, faq
  - `is_published`: true, false
  - `search`: Search by title

- **Response**:
```json
[
  {
    "id": 1,
    "title": "How to Buy Crypto",
    "content": "Step by step guide...",
    "category": "trading",
    "video_url": "https://youtube.com/watch?v=...",
    "slug": "how-to-buy-crypto",
    "excerpt": "Learn how to buy cryptocurrency...",
    "thumbnail": "http://localhost:8000/media/tutorials/thumbnails/thumb1.jpg",
    "order": 1,
    "is_published": true,
    "author": 1,
    "views": 150,
    "created_at": "2024-11-16T09:00:00Z",
    "updated_at": "2024-11-16T09:00:00Z"
  }
]
```

### Create Tutorial
- **POST** `/api/tutorials/`
- **Admin Only**: Yes
- **Body**:
```json
{
  "title": "Getting Started with Crypto",
  "content": "Welcome to crypto trading...",
  "category": "getting_started",
  "video_url": "https://youtube.com/watch?v=...",
  "slug": "getting-started-crypto",
  "excerpt": "A beginner's guide",
  "is_published": true
}
```

### Get Tutorial Details
- **GET** `/api/tutorials/{id}/`

### Update Tutorial
- **PUT/PATCH** `/api/tutorials/{id}/`
- **Admin Only**: Yes

### Delete Tutorial
- **DELETE** `/api/tutorials/{id}/`
- **Admin Only**: Yes

---

## 7. Notification Endpoints

### List Notifications
- **GET** `/api/notifications/`
- **Query Parameters**:
  - `read`: true, false
  - `ordering`: created_at, -created_at

- **Response**:
```json
[
  {
    "id": 1,
    "user": 1,
    "message": "Your crypto transaction has been approved",
    "read": false,
    "notification_type": "ORDER_COMPLETED",
    "title": "Transaction Approved",
    "created_at": "2024-11-16T12:00:00Z"
  }
]
```

### Create Notification
- **POST** `/api/notifications/`
- **Admin Only**: Yes
- **Body**:
```json
{
  "message": "System maintenance scheduled",
  "notification_type": "SYSTEM",
  "title": "Maintenance Notice"
}
```

### Get Notification Details
- **GET** `/api/notifications/{id}/`

### Mark as Read
- **PATCH** `/api/notifications/{id}/`
- **Body**:
```json
{
  "read": true
}
```

### Delete Notification
- **DELETE** `/api/notifications/{id}/`

---

## 8. Settings Endpoints

### Get Current Settings
- **GET** `/api/analytics/settings/current/`
- **Public**: Yes (read-only)
- **Response**:
```json
{
  "id": 1,
  "live_rate_source": "coinmarketcap",
  "escrow_percent": "2.00",
  "support_contacts": {
    "email": "support@example.com",
    "phone": "+233123456789",
    "whatsapp": "+233987654321"
  },
  "updated_at": "2024-11-16T08:00:00Z"
}
```

### List All Settings
- **GET** `/api/analytics/settings/`
- **Admin Only**: Yes

### Update Settings
- **PUT/PATCH** `/api/analytics/settings/{id}/`
- **Admin Only**: Yes
- **Body**:
```json
{
  "live_rate_source": "binance",
  "escrow_percent": "2.50",
  "support_contacts": {
    "email": "support@example.com",
    "phone": "+233123456789",
    "whatsapp": "+233987654321",
    "telegram": "@support"
  }
}
```

---

## 9. Analytics Endpoints

### Get Dashboard Metrics
- **GET** `/api/analytics/metrics/dashboard/`
- **Response**:
```json
{
  "metrics": {
    "id": 1,
    "user": 1,
    "total_trades": 25,
    "total_volume": "50000.00000000",
    "total_profit": "5000.00000000",
    "last_trade_at": "2024-11-16T11:30:00Z",
    "updated_at": "2024-11-16T12:00:00Z"
  },
  "stats": {
    "total_orders": 30,
    "pending_orders": 5,
    "completed_orders": 20,
    "total_trades": 25,
    "total_volume": "50000.00",
    "recent_trades": [...]
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "field_name": [
    "This field is required."
  ]
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "error": "Admin permission required"
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "detail": "Error message"
}
```

---

## Pagination

All list endpoints support pagination:

**Request:**
```
GET /api/wallets/crypto-transactions/?page=2&page_size=20
```

**Response:**
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/wallets/crypto-transactions/?page=3",
  "previous": "http://localhost:8000/api/wallets/crypto-transactions/?page=1",
  "results": [...]
}
```

---

## Filtering & Ordering

Most list endpoints support filtering and ordering:

**Examples:**
```
# Filter by status
GET /api/wallets/crypto-transactions/?status=pending

# Search by reference
GET /api/wallets/crypto-transactions/?search=TXN-001

# Order by created_at descending
GET /api/wallets/crypto-transactions/?ordering=-created_at

# Combine filters
GET /api/wallets/crypto-transactions/?status=approved&payment_method=momo&ordering=-created_at
```

---

## Testing with cURL

### Register User
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "password2": "SecurePass123",
    "phone": "+233123456789"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123"
  }'
```

### Get My Wallet
```bash
curl -X GET http://localhost:8000/api/wallets/wallets/my_wallet/ \
  -H "Authorization: Bearer <access_token>"
```

### Create Crypto Transaction
```bash
curl -X POST http://localhost:8000/api/wallets/crypto-transactions/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "buy",
    "cedis_amount": "1000.00",
    "crypto_amount": "0.025",
    "rate": "40000.00",
    "payment_method": "momo",
    "reference": "TXN-20241116-001"
  }'
```

---

## Rate Limiting

API endpoints may be rate-limited. Default limits:
- Anonymous users: 100 requests/hour
- Authenticated users: 1000 requests/hour
- Admin users: Unlimited

---

## CORS

The API supports CORS for the following origins:
- http://localhost:3000
- http://127.0.0.1:3000

Configure additional origins in the `.env` file.
