# Escrow Release Guarantee System

## Overview
This document describes the comprehensive system implemented to ensure escrow funds are always released when P2P transactions are completed, preventing funds from being stuck in escrow.

## Problem
Previously, transactions could be marked as "completed" without releasing escrow, causing funds to be locked indefinitely. This happened when:
- Transactions were manually marked as completed (e.g., via admin)
- The auto-release command didn't run
- Status was changed programmatically without releasing escrow

## Solution - Multi-Layer Protection

### 1. Signal Handler (Primary Safety Net)
**File:** `backend/orders/signals.py`

A `pre_save` signal handler automatically releases escrow when a transaction's status changes to 'completed':

- **Trigger:** When `P2PServiceTransaction.status` changes to 'completed' and `escrow_released=False`
- **Action:** 
  - Deducts escrow from buyer's wallet
  - Credits seller's wallet
  - Creates wallet transaction records
  - Marks `escrow_released=True` and sets `escrow_released_at`
  - Logs the action

**Benefits:**
- Works even if transaction is manually marked as completed
- Prevents data inconsistency
- Runs synchronously during save operation

### 2. Enhanced Auto-Release Command (Secondary Safety Net)
**File:** `backend/orders/management/commands/process_p2p_auto_actions.py`

The auto-release command now has two functions:

#### A. Normal Auto-Release (Existing)
- Processes transactions in 'verifying' status after 1 hour
- Releases escrow and marks as completed

#### B. Safety Net for Completed Transactions (New)
- Checks for transactions with `status='completed'` and `escrow_released=False`
- Releases escrow for any completed transactions that somehow missed release
- Runs every time the command executes

**Benefits:**
- Catches edge cases missed by signal handler
- Provides recovery mechanism
- Can be run manually to fix stuck escrow

### 3. Escrow Release Tracking Fields
**Migration:** `0016_add_escrow_release_tracking.py`

New fields added to `P2PServiceTransaction`:
- `escrow_released` (Boolean): Tracks if escrow has been released
- `escrow_released_at` (DateTime): Timestamp of when escrow was released

**Benefits:**
- Prevents duplicate releases
- Provides audit trail
- Enables querying for stuck transactions

### 4. Diagnostic Command
**File:** `backend/orders/management/commands/check_escrow.py`

A diagnostic tool to identify escrow issues:
```bash
python manage.py check_escrow <user_email>
```

Shows:
- Wallet balance breakdown
- All transactions holding escrow
- Completed transactions with unreleased escrow
- Discrepancies between actual and calculated escrow

### 5. Manual Fix Command
**File:** `backend/orders/management/commands/fix_escrow_release.py`

Manual tool to release escrow for specific transactions:
```bash
python manage.py fix_escrow_release <transaction_reference>
```

## Setup Requirements

### 1. Run Migrations
```bash
python manage.py migrate
```

### 2. Schedule Auto-Release Command
The `process_p2p_auto_actions` command should run every 5-10 minutes.

**Using Cron (Linux/Mac):**
```cron
*/5 * * * * cd /path/to/project/backend && python manage.py process_p2p_auto_actions
```

**Using Windows Task Scheduler:**
- Create a task that runs every 5 minutes
- Command: `python manage.py process_p2p_auto_actions`
- Start in: `C:\path\to\project\backend`

**Using Celery (Recommended for Production):**
```python
# In celery.py or tasks.py
@periodic_task(run_every=timedelta(minutes=5))
def process_p2p_auto_actions():
    call_command('process_p2p_auto_actions')
```

## How It Works

### Normal Flow:
1. Buyer verifies service → Status: 'verifying', `auto_release_at` set
2. Auto-release command runs → Releases escrow, Status: 'completed', `escrow_released=True`

### Edge Case Protection:
1. Transaction manually marked as 'completed' → Signal handler releases escrow immediately
2. Signal handler fails → Auto-release command catches it on next run
3. Both fail → Manual fix command available

## Monitoring

### Check for Stuck Escrow:
```bash
python manage.py check_escrow <user_email>
```

### Check All Users:
```python
# In Django shell
from wallets.models import Wallet
from orders.p2p_models import P2PServiceTransaction

# Find wallets with escrow but no active transactions
wallets_with_escrow = Wallet.objects.filter(escrow_balance__gt=0)
for wallet in wallets_with_escrow:
    active_txns = P2PServiceTransaction.objects.filter(
        buyer=wallet.user,
        status__in=['payment_received', 'service_provided', 'verifying'],
        escrow_amount_cedis__gt=0
    )
    if not active_txns.exists():
        print(f"Potential stuck escrow for {wallet.user.email}: GHS {wallet.escrow_balance}")
```

## Testing

### Test Signal Handler:
```python
# In Django shell
from orders.p2p_models import P2PServiceTransaction
from wallets.models import Wallet

txn = P2PServiceTransaction.objects.get(reference='PPT-XXXXX')
wallet_before = Wallet.objects.get(user=txn.buyer)

# Manually set to completed (should trigger signal)
txn.status = 'completed'
txn.save()

wallet_after = Wallet.objects.get(user=txn.buyer)
assert wallet_after.escrow_balance < wallet_before.escrow_balance
assert txn.escrow_released == True
```

### Test Auto-Release Command:
```bash
python manage.py process_p2p_auto_actions
```

## Troubleshooting

### Escrow Still Stuck?
1. Run diagnostic: `python manage.py check_escrow <email>`
2. Check for completed transactions with `escrow_released=False`
3. Run auto-release command: `python manage.py process_p2p_auto_actions`
4. If still stuck, use manual fix: `python manage.py fix_escrow_release <ref>`

### Signal Not Firing?
- Check `backend/orders/apps.py` - signals should be imported in `ready()`
- Restart Django server
- Check logs for signal errors

## Summary

The system now has **4 layers of protection**:
1. ✅ Signal handler (automatic on save)
2. ✅ Auto-release command (scheduled)
3. ✅ Safety net in auto-release (catches edge cases)
4. ✅ Manual fix command (admin tool)

**Result:** Escrow will be released in all scenarios, preventing funds from being stuck.

