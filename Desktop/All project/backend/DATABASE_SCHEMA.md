# Database Schema Documentation

## Overview
This document describes the PostgreSQL database schema for the Crypto Buy and Sell platform.

---

## Tables

### 1. users
**Primary Model:** `authentication.User`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing user ID |
| username | VARCHAR(150) | UNIQUE, NOT NULL | Username for login |
| email | VARCHAR(254) | UNIQUE, NOT NULL | User email (used for login) |
| phone | VARCHAR(20) | NULL | User phone number |
| password | VARCHAR(128) | NOT NULL | Hashed password |
| password_hash | VARCHAR(255) | NULL | Additional password hash field |
| role | VARCHAR(10) | NOT NULL, DEFAULT 'user' | User role: 'user' or 'admin' |
| kyc_status | VARCHAR(10) | NOT NULL, DEFAULT 'pending' | KYC status: 'pending', 'approved', 'rejected' |
| first_name | VARCHAR(150) | NULL | User's first name |
| last_name | VARCHAR(150) | NULL | User's last name |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Account active status |
| is_staff | BOOLEAN | NOT NULL, DEFAULT FALSE | Staff status |
| is_superuser | BOOLEAN | NOT NULL, DEFAULT FALSE | Superuser status |
| date_joined | TIMESTAMP | NOT NULL | Account creation date |
| created_at | TIMESTAMP | NOT NULL | Record creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Record update timestamp |

**Indexes:**
- `users_email_idx` on (email)
- `users_username_idx` on (username)

---

### 2. wallets
**Primary Model:** `wallets.Wallet`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing wallet ID |
| user_id | BIGINT | FOREIGN KEY, UNIQUE | Reference to users.id |
| balance_cedis | DECIMAL(20,2) | NOT NULL, DEFAULT 0 | Balance in Cedis |
| balance_crypto | DECIMAL(20,8) | NOT NULL, DEFAULT 0 | Balance in cryptocurrency |
| escrow_balance | DECIMAL(20,2) | NOT NULL, DEFAULT 0 | Amount in escrow |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)

**Indexes:**
- `wallets_user_id_idx` on (user_id)

---

### 3. crypto_transactions
**Primary Model:** `wallets.CryptoTransaction`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing transaction ID |
| user_id | BIGINT | FOREIGN KEY | Reference to users.id |
| type | VARCHAR(10) | NOT NULL | Transaction type: 'buy' or 'sell' |
| cedis_amount | DECIMAL(20,2) | NOT NULL | Amount in Cedis |
| crypto_amount | DECIMAL(20,8) | NOT NULL | Amount in cryptocurrency |
| rate | DECIMAL(20,2) | NOT NULL | Exchange rate |
| status | VARCHAR(10) | NOT NULL, DEFAULT 'pending' | Status: 'pending', 'approved', 'declined' |
| payment_method | VARCHAR(10) | NOT NULL | Payment method: 'momo', 'bank', 'crypto' |
| reference | VARCHAR(255) | UNIQUE, NOT NULL | Transaction reference |
| created_at | TIMESTAMP | NOT NULL | Transaction creation timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)

**Indexes:**
- `crypto_transactions_user_id_idx` on (user_id)
- `crypto_transactions_reference_idx` on (reference)
- `crypto_transactions_status_idx` on (status)
- `crypto_transactions_created_at_idx` on (created_at DESC)

---

### 4. gift_cards
**Primary Model:** `orders.GiftCard`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing gift card ID |
| name | VARCHAR(255) | NOT NULL | Gift card name |
| brand | VARCHAR(100) | NOT NULL | Gift card brand |
| rate_buy | DECIMAL(10,2) | NOT NULL | Buying rate |
| rate_sell | DECIMAL(10,2) | NOT NULL | Selling rate |
| image | VARCHAR(100) | NULL | Path to gift card image |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Active status |
| created_at | TIMESTAMP | NOT NULL | Record creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Record update timestamp |

**Indexes:**
- `gift_cards_brand_idx` on (brand)
- `gift_cards_is_active_idx` on (is_active)

---

### 5. gift_card_orders
**Primary Model:** `orders.GiftCardOrder`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing order ID |
| user_id | BIGINT | FOREIGN KEY | Reference to users.id |
| card_id | BIGINT | FOREIGN KEY | Reference to gift_cards.id |
| amount | DECIMAL(20,2) | NOT NULL | Order amount |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | Status: 'pending', 'approved', 'declined', 'completed' |
| proof_image | VARCHAR(100) | NOT NULL | Path to proof image |
| created_at | TIMESTAMP | NOT NULL | Order creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Order update timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)
- `card_id` → `gift_cards.id` (PROTECT)

**Indexes:**
- `gift_card_orders_user_id_idx` on (user_id)
- `gift_card_orders_card_id_idx` on (card_id)
- `gift_card_orders_status_idx` on (status)
- `gift_card_orders_created_at_idx` on (created_at DESC)

---

### 6. orders
**Primary Model:** `orders.Order`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing order ID |
| user_id | BIGINT | FOREIGN KEY | Reference to users.id |
| order_type | VARCHAR(10) | NOT NULL | Order type: 'BUY' or 'SELL' |
| currency_pair | VARCHAR(20) | NOT NULL | Trading pair (e.g., 'BTC/USDT') |
| amount | DECIMAL(20,8) | NOT NULL | Order amount |
| price | DECIMAL(20,8) | NOT NULL | Order price |
| total | DECIMAL(20,8) | NOT NULL | Total value |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING' | Status: 'PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', 'FAILED' |
| created_at | TIMESTAMP | NOT NULL | Order creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Order update timestamp |
| completed_at | TIMESTAMP | NULL | Order completion timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)

**Indexes:**
- `orders_user_id_idx` on (user_id)
- `orders_status_idx` on (status)
- `orders_created_at_idx` on (created_at DESC)

---

### 7. trades
**Primary Model:** `orders.Trade`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing trade ID |
| order_id | BIGINT | FOREIGN KEY | Reference to orders.id |
| buyer_id | BIGINT | FOREIGN KEY | Reference to users.id (buyer) |
| seller_id | BIGINT | FOREIGN KEY | Reference to users.id (seller) |
| amount | DECIMAL(20,8) | NOT NULL | Trade amount |
| price | DECIMAL(20,8) | NOT NULL | Trade price |
| total | DECIMAL(20,8) | NOT NULL | Total value |
| created_at | TIMESTAMP | NOT NULL | Trade creation timestamp |

**Foreign Keys:**
- `order_id` → `orders.id` (CASCADE)
- `buyer_id` → `users.id` (CASCADE)
- `seller_id` → `users.id` (CASCADE)

**Indexes:**
- `trades_order_id_idx` on (order_id)
- `trades_buyer_id_idx` on (buyer_id)
- `trades_seller_id_idx` on (seller_id)
- `trades_created_at_idx` on (created_at DESC)

---

### 8. tutorials
**Primary Model:** `tutorials.Tutorial`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing tutorial ID |
| title | VARCHAR(255) | NOT NULL | Tutorial title |
| content | TEXT | NOT NULL | Tutorial content |
| category | VARCHAR(50) | NOT NULL | Category: 'getting_started', 'trading', 'wallet', 'security', 'faq' |
| video_url | VARCHAR(200) | NULL | URL to tutorial video |
| slug | VARCHAR(50) | UNIQUE, NOT NULL | URL-friendly slug |
| excerpt | TEXT | NULL | Short description |
| thumbnail | VARCHAR(100) | NULL | Path to thumbnail image |
| order | INTEGER | NOT NULL, DEFAULT 0 | Display order |
| is_published | BOOLEAN | NOT NULL, DEFAULT FALSE | Published status |
| author_id | BIGINT | FOREIGN KEY, NULL | Reference to users.id |
| views | INTEGER | NOT NULL, DEFAULT 0 | View count |
| created_at | TIMESTAMP | NOT NULL | Tutorial creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Tutorial update timestamp |

**Foreign Keys:**
- `author_id` → `users.id` (SET NULL)

**Indexes:**
- `tutorials_slug_idx` on (slug)
- `tutorials_category_idx` on (category)
- `tutorials_is_published_idx` on (is_published)
- `tutorials_order_idx` on (order)

---

### 9. tutorial_progress
**Primary Model:** `tutorials.TutorialProgress`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing progress ID |
| user_id | BIGINT | FOREIGN KEY | Reference to users.id |
| tutorial_id | BIGINT | FOREIGN KEY | Reference to tutorials.id |
| is_completed | BOOLEAN | NOT NULL, DEFAULT FALSE | Completion status |
| completed_at | TIMESTAMP | NULL | Completion timestamp |
| created_at | TIMESTAMP | NOT NULL | Record creation timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)
- `tutorial_id` → `tutorials.id` (CASCADE)

**Unique Constraints:**
- UNIQUE(user_id, tutorial_id)

---

### 10. notifications
**Primary Model:** `notifications.Notification`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing notification ID |
| user_id | BIGINT | FOREIGN KEY | Reference to users.id |
| message | TEXT | NOT NULL | Notification message |
| read | BOOLEAN | NOT NULL, DEFAULT FALSE | Read status |
| notification_type | VARCHAR(50) | NULL | Type: 'ORDER_COMPLETED', 'KYC_APPROVED', etc. |
| title | VARCHAR(255) | NULL | Notification title |
| created_at | TIMESTAMP | NOT NULL | Notification creation timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)

**Indexes:**
- `notifications_user_id_idx` on (user_id)
- `notifications_read_idx` on (read)
- `notifications_created_at_idx` on (created_at DESC)

---

### 11. settings
**Primary Model:** `analytics.Settings`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing settings ID |
| live_rate_source | VARCHAR(255) | NOT NULL, DEFAULT 'coinmarketcap' | Source for live rates |
| escrow_percent | DECIMAL(5,2) | NOT NULL, DEFAULT 2.0 | Escrow percentage |
| support_contacts | JSONB | NOT NULL, DEFAULT '{}' | Support contact information |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

**Note:** Typically only one record exists in this table.

---

### 12. analytics_events
**Primary Model:** `analytics.AnalyticsEvent`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing event ID |
| user_id | BIGINT | FOREIGN KEY, NULL | Reference to users.id |
| event_type | VARCHAR(50) | NOT NULL | Event type |
| event_name | VARCHAR(255) | NOT NULL | Event name |
| properties | JSONB | NOT NULL, DEFAULT '{}' | Event properties |
| session_id | VARCHAR(255) | NULL | Session identifier |
| ip_address | INET | NULL | User IP address |
| user_agent | TEXT | NULL | User agent string |
| created_at | TIMESTAMP | NOT NULL | Event timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (SET NULL)

**Indexes:**
- `analytics_events_event_type_created_at_idx` on (event_type, created_at)
- `analytics_events_user_id_created_at_idx` on (user_id, created_at)

---

### 13. user_metrics
**Primary Model:** `analytics.UserMetric`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing metric ID |
| user_id | BIGINT | FOREIGN KEY, UNIQUE | Reference to users.id |
| total_trades | INTEGER | NOT NULL, DEFAULT 0 | Total number of trades |
| total_volume | DECIMAL(20,8) | NOT NULL, DEFAULT 0 | Total trading volume |
| total_profit | DECIMAL(20,8) | NOT NULL, DEFAULT 0 | Total profit/loss |
| last_trade_at | TIMESTAMP | NULL | Last trade timestamp |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)

---

### 14. kyc_verifications
**Primary Model:** `kyc.KYCVerification`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PRIMARY KEY | Auto-incrementing KYC ID |
| user_id | BIGINT | FOREIGN KEY, UNIQUE | Reference to users.id |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING' | Status: 'PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED' |
| document_type | VARCHAR(20) | NOT NULL | Type: 'PASSPORT', 'DRIVER_LICENSE', 'NATIONAL_ID' |
| document_number | VARCHAR(100) | NOT NULL | Document number |
| first_name | VARCHAR(100) | NOT NULL | User's first name |
| last_name | VARCHAR(100) | NOT NULL | User's last name |
| date_of_birth | DATE | NOT NULL | Date of birth |
| address | TEXT | NOT NULL | Physical address |
| document_front | VARCHAR(100) | NOT NULL | Path to front document image |
| document_back | VARCHAR(100) | NULL | Path to back document image |
| selfie | VARCHAR(100) | NOT NULL | Path to selfie image |
| rejection_reason | TEXT | NULL | Reason for rejection |
| reviewed_by_id | BIGINT | FOREIGN KEY, NULL | Reference to users.id (reviewer) |
| submitted_at | TIMESTAMP | NOT NULL | Submission timestamp |
| reviewed_at | TIMESTAMP | NULL | Review timestamp |

**Foreign Keys:**
- `user_id` → `users.id` (CASCADE)
- `reviewed_by_id` → `users.id` (SET NULL)

**Indexes:**
- `kyc_verifications_user_id_idx` on (user_id)
- `kyc_verifications_status_idx` on (status)

---

## Relationships

### One-to-One
- `User` → `Wallet` (One user has one wallet)
- `User` → `UserMetric` (One user has one metric record)
- `User` → `KYCVerification` (One user has one KYC record)

### One-to-Many
- `User` → `CryptoTransaction` (One user can have many transactions)
- `User` → `GiftCardOrder` (One user can have many gift card orders)
- `User` → `Order` (One user can have many orders)
- `User` → `Notification` (One user can have many notifications)
- `User` → `Tutorial` (as author - one user can author many tutorials)
- `GiftCard` → `GiftCardOrder` (One gift card can have many orders)
- `Order` → `Trade` (One order can have many trades)
- `Tutorial` → `TutorialProgress` (One tutorial can have many progress records)

### Many-to-Many (through tables)
- `User` ↔ `Tutorial` (through `TutorialProgress`)

---

## Database Diagram (Text)

```
users
  ├── wallets (1:1)
  ├── crypto_transactions (1:N)
  ├── gift_card_orders (1:N)
  ├── orders (1:N)
  │   └── trades (1:N)
  ├── notifications (1:N)
  ├── tutorials (1:N, as author)
  ├── tutorial_progress (1:N)
  ├── user_metrics (1:1)
  └── kyc_verifications (1:1)

gift_cards
  └── gift_card_orders (1:N)

tutorials
  └── tutorial_progress (1:N)
```

---

## Database Size Estimates

For a platform with 10,000 users:

| Table | Est. Rows | Est. Size |
|-------|-----------|-----------|
| users | 10,000 | 2 MB |
| wallets | 10,000 | 500 KB |
| crypto_transactions | 100,000 | 20 MB |
| gift_cards | 100 | 50 KB |
| gift_card_orders | 50,000 | 10 MB |
| orders | 200,000 | 40 MB |
| trades | 150,000 | 30 MB |
| tutorials | 50 | 200 KB |
| notifications | 500,000 | 100 MB |
| settings | 1 | 1 KB |
| analytics_events | 1,000,000 | 200 MB |
| **Total** | | **~400 MB** |

---

## Backup & Maintenance

### Backup Command
```bash
pg_dump -U postgres crypto_platform > backup_$(date +%Y%m%d).sql
```

### Restore Command
```bash
psql -U postgres crypto_platform < backup_20241116.sql
```

### Maintenance
```sql
-- Vacuum and analyze
VACUUM ANALYZE;

-- Reindex
REINDEX DATABASE crypto_platform;

-- Check table sizes
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Indexes Optimization

Critical indexes for performance:
1. `crypto_transactions_created_at_idx` - For transaction history
2. `notifications_user_id_read_idx` - For unread notifications
3. `orders_user_id_status_idx` - For order filtering
4. `analytics_events_event_type_created_at_idx` - For analytics queries

Consider adding indexes based on query patterns in production.
