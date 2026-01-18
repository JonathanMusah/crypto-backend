# Gift Card System Implementation

## Overview
Complete backend implementation of the gift card system with CRUD operations, order management, proof image upload, and rate management.

## Models

### GiftCard
- **Fields**: name, brand, rate_buy, rate_sell, image, is_active, created_at, updated_at
- **Purpose**: Stores gift card types and their buy/sell rates

### GiftCardOrder
- **Fields**: 
  - user (ForeignKey)
  - card (ForeignKey to GiftCard)
  - order_type (choices: 'buy', 'sell')
  - amount (DecimalField)
  - status (choices: 'pending', 'approved', 'declined', 'completed')
  - proof_image (ImageField, optional)
  - created_at, updated_at
- **Properties**:
  - `calculated_amount`: Automatically calculates amount based on order type and card rate

## API Endpoints

### Gift Cards

#### List Gift Cards
- **URL**: `/api/orders/giftcards/list/` or `/api/orders/giftcards/`
- **Method**: GET
- **Auth**: Public (only active cards shown to non-admin)
- **Response**: List of gift cards with image URLs

#### Create Gift Card (Admin Only)
- **URL**: `/api/orders/giftcards/`
- **Method**: POST
- **Auth**: Admin only
- **Body**: { name, brand, rate_buy, rate_sell, image (optional), is_active }

#### Update Gift Card (Admin Only)
- **URL**: `/api/orders/giftcards/{id}/`
- **Method**: PUT/PATCH
- **Auth**: Admin only

#### Update Gift Card Rates (Admin Only)
- **URL**: `/api/orders/giftcards/{id}/update_rates/`
- **Method**: PATCH
- **Auth**: Admin only
- **Body**: { rate_buy, rate_sell }

#### Delete Gift Card (Admin Only)
- **URL**: `/api/orders/giftcards/{id}/`
- **Method**: DELETE
- **Auth**: Admin only

### Gift Card Orders

#### List Orders
- **URL**: `/api/orders/giftcard-orders/`
- **Method**: GET
- **Auth**: Authenticated
- **Response**: User's own orders (admin sees all)
- **Filters**: status, card, order_type
- **Query Params**: ?status=pending&order_type=buy

#### Create Order
- **URL**: `/api/orders/giftcard-orders/order/` or `/api/orders/giftcards/order/`
- **Method**: POST
- **Auth**: Authenticated
- **Body**: 
  ```json
  {
    "card": 1,
    "order_type": "buy",
    "amount": "100.00"
  }
  ```
- **Response**: Created order with calculated_amount

#### Upload Proof Image
- **URL**: `/api/orders/giftcards/upload-proof/{order_id}/` or `/api/orders/giftcard-orders/{id}/upload_proof/`
- **Method**: POST
- **Auth**: Authenticated (own orders only, or admin)
- **Content-Type**: multipart/form-data
- **Body**: Form data with `proof_image` file
- **Validation**: 
  - File must be an image
  - Max size: 10MB

#### Update Order Status (Admin Only)
- **URL**: `/api/orders/giftcard-orders/{id}/update_status/`
- **Method**: PATCH
- **Auth**: Admin only
- **Body**: 
  ```json
  {
    "status": "approved"
  }
  ```
- **Valid Statuses**: pending, approved, declined, completed

#### Approve Order (Admin Only)
- **URL**: `/api/orders/giftcard-orders/{id}/approve/`
- **Method**: POST
- **Auth**: Admin only

#### Decline Order (Admin Only)
- **URL**: `/api/orders/giftcard-orders/{id}/decline/`
- **Method**: POST
- **Auth**: Admin only

## Frontend API Structure

The following endpoints match the frontend API structure:

1. **GET** `/api/orders/giftcards/list/` - List all active gift cards
2. **POST** `/api/orders/giftcards/order/` - Create a new gift card order
3. **POST** `/api/orders/giftcards/upload-proof/{order_id}/` - Upload proof image

## Features

### CRUD Operations
- ✅ Full CRUD for gift cards (admin only for create/update/delete)
- ✅ Public listing of active gift cards
- ✅ Gift card order management

### Order Management
- ✅ Create buy/sell gift card orders
- ✅ Automatic calculation of amounts based on rates
- ✅ Order status tracking (pending, approved, declined, completed)

### Proof Image Upload
- ✅ Upload proof images for orders
- ✅ File type validation (images only)
- ✅ File size validation (max 10MB)
- ✅ Secure access (users can only upload for their own orders)

### Rate Management
- ✅ Admin can update gift card rates
- ✅ Separate buy and sell rates
- ✅ Rate validation (must be > 0)

### Status Updates
- ✅ Admin can update order status
- ✅ Specific approve/decline endpoints
- ✅ Status validation
- ✅ Automatic notifications on status changes

### Notifications
- ✅ Notifications created on:
  - Order creation
  - Proof image upload
  - Status updates (approved, declined, completed)

## Serializers

### GiftCardSerializer
- Includes image URL generation
- Public fields: id, name, brand, rate_buy, rate_sell, image_url, is_active

### GiftCardOrderSerializer
- Includes calculated_amount
- Includes proof_image_url
- Includes card details (name, brand)

### GiftCardOrderCreateSerializer
- Simplified serializer for order creation
- Validates card is active
- Validates amount > 0

### GiftCardRateUpdateSerializer
- Admin-only serializer for rate updates
- Validates rates > 0

## Permissions

- **Gift Cards**:
  - List/Retrieve: Public
  - Create/Update/Delete: Admin only

- **Gift Card Orders**:
  - List: Authenticated (own orders)
  - Create: Authenticated
  - Upload Proof: Authenticated (own orders)
  - Status Update: Admin only

## Database Migration

After implementation, run:
```bash
python manage.py makemigrations orders
python manage.py migrate
```

This will create a migration for:
- Adding `order_type` field to GiftCardOrder
- Making `proof_image` optional (blank=True, null=True)

## Admin Interface

The Django admin interface has been updated to include:
- Order type in list display
- Order type in filters
- Calculated amount in readonly fields
- Improved fieldsets for better organization

## Example Usage

### Create a Gift Card (Admin)
```bash
POST /api/orders/giftcards/
{
  "name": "Amazon $100",
  "brand": "Amazon",
  "rate_buy": 0.95,
  "rate_sell": 0.90,
  "is_active": true
}
```

### Create an Order
```bash
POST /api/orders/giftcards/order/
{
  "card": 1,
  "order_type": "buy",
  "amount": "100.00"
}
```

### Upload Proof
```bash
POST /api/orders/giftcards/upload-proof/1/
Content-Type: multipart/form-data
proof_image: <file>
```

### Update Rates (Admin)
```bash
PATCH /api/orders/giftcards/1/update_rates/
{
  "rate_buy": 0.96,
  "rate_sell": 0.91
}
```

### Update Status (Admin)
```bash
PATCH /api/orders/giftcard-orders/1/update_status/
{
  "status": "approved"
}
```

