from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.cache import cache
import secrets
import hashlib
from datetime import timedelta


class User(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    
    KYC_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True)  # Handled by Django's set_password
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    kyc_status = models.CharField(max_length=10, choices=KYC_STATUS_CHOICES, default='pending')
    onboarding_completed = models.BooleanField(default=False)
    
    # Profile Verification
    email_verified = models.BooleanField(default=False, help_text="Email verification status (required)")
    email_verified_at = models.DateTimeField(null=True, blank=True, help_text="When email was verified")
    phone_verified = models.BooleanField(default=False, help_text="Phone verification status (optional)")
    phone_verified_at = models.DateTimeField(null=True, blank=True, help_text="When phone was verified")
    
    # Trust Score & Reputation System
    successful_trades = models.IntegerField(default=0, help_text="Number of successfully completed gift card trades")
    disputes_filed = models.IntegerField(default=0, help_text="Number of disputes filed by this user")
    disputes_against = models.IntegerField(default=0, help_text="Number of disputes filed against this user")
    trust_score = models.IntegerField(default=0, help_text="Trust score calculated from trades, disputes, and verification")
    trust_score_override = models.IntegerField(null=True, blank=True, help_text="Admin override for trust score (if set, this value is used instead of calculated score)")
    
    # Seller Status for P2P Services
    SELLER_STATUS_CHOICES = [
        ('not_applied', 'Not Applied'),
        ('pending', 'Application Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),
    ]
    can_sell_p2p = models.BooleanField(default=False, help_text="Whether user can create sell listings for P2P services")
    seller_status = models.CharField(max_length=20, choices=SELLER_STATUS_CHOICES, default='not_applied', help_text="Current seller application status")
    seller_approved_at = models.DateTimeField(null=True, blank=True, help_text="When seller application was approved")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(null=True, blank=True, help_text="Last time user was seen online")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def update_last_seen(self):
        """Update user's last seen timestamp"""
        from django.utils import timezone
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])
    
    def is_online(self):
        """Check if user is currently online (active within last 3 minutes)"""
        if not self.last_seen:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() - self.last_seen < timedelta(minutes=3)
    
    def get_status(self):
        """Get user's online status with more granular information"""
        if not self.last_seen:
            return {'status': 'offline', 'label': 'Offline'}
        
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        time_diff = now - self.last_seen
        
        # Online: within last 3 minutes
        if time_diff < timedelta(minutes=3):
            return {'status': 'online', 'label': 'Online'}
        
        # Away: 3-60 minutes ago - show exact minutes
        elif time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() / 60)
            if minutes < 5:
                return {'status': 'away', 'label': f'Last seen {minutes} minute{"s" if minutes > 1 else ""} ago'}
            elif minutes < 30:
                return {'status': 'away', 'label': f'Last seen {minutes} minutes ago'}
            else:
                return {'status': 'away', 'label': f'Last seen {minutes} minutes ago'}
        
        # Offline: 1-6 hours ago - show hours and minutes
        elif time_diff < timedelta(hours=6):
            hours = int(time_diff.total_seconds() / 3600)
            minutes = int((time_diff.total_seconds() % 3600) / 60)
            if hours == 1:
                if minutes > 0:
                    return {'status': 'offline', 'label': f'Last seen 1 hour {minutes} minute{"s" if minutes != 1 else ""} ago'}
                else:
                    return {'status': 'offline', 'label': 'Last seen 1 hour ago'}
            elif hours < 6:
                # For first few hours, show hours and minutes
                if minutes >= 30:
                    return {'status': 'offline', 'label': f'Last seen {hours} hour{"s" if hours != 1 else ""} {minutes} minutes ago'}
                elif minutes > 0:
                    return {'status': 'offline', 'label': f'Last seen {hours} hour{"s" if hours != 1 else ""} {minutes} minute{"s" if minutes != 1 else ""} ago'}
                else:
                    return {'status': 'offline', 'label': f'Last seen {hours} hour{"s" if hours != 1 else ""} ago'}
        
        # Offline: 6-24 hours ago - show time (e.g., "Last seen at 14:30")
        elif time_diff < timedelta(hours=24):
            return {'status': 'offline', 'label': f'Last seen at {self.last_seen.strftime("%H:%M")}'}
        
        # Offline: 1-7 days ago - show days with time
        elif time_diff < timedelta(days=7):
            days = int(time_diff.total_seconds() / 86400)
            if days == 1:
                return {'status': 'offline', 'label': f'Last seen yesterday at {self.last_seen.strftime("%H:%M")}'}
            elif days == 2:
                return {'status': 'offline', 'label': f'Last seen 2 days ago at {self.last_seen.strftime("%H:%M")}'}
            elif days < 7:
                return {'status': 'offline', 'label': f'Last seen {days} days ago at {self.last_seen.strftime("%H:%M")}'}
            else:
                return {'status': 'offline', 'label': f'Last seen {self.last_seen.strftime("%b %d")} at {self.last_seen.strftime("%H:%M")}'}
        
        # Offline: more than 7 days - show date
        else:
            days = int(time_diff.total_seconds() / 86400)
            if days < 30:
                return {'status': 'offline', 'label': f'Last seen {self.last_seen.strftime("%b %d")}'}
            elif days < 365:
                return {'status': 'offline', 'label': f'Last seen {self.last_seen.strftime("%b %d, %Y")}'}
            else:
                return {'status': 'offline', 'label': f'Last seen {self.last_seen.strftime("%b %d, %Y")}'}

    class Meta:
        db_table = 'users'
    
    def __str__(self):
        return self.email
    
    def calculate_trust_score(self):
        """
        Calculate trust score based on:
        - +1 for each completed gift card trade
        - -2 for disputes filed
        - -3 for disputes lost (against user)
        - -5 for fraudulent or duplicate gift card detection
        - +1 for verified email
        - Ratings: Average rating affects score
          * 5 stars: +2 points per rating
          * 4 stars: +1 point per rating
          * 3 stars: 0 points
          * 2 stars: -1 point per rating
          * 1 star: -2 points per rating
        """
        score = 0
        
        # Base score from successful trades
        score += self.successful_trades
        
        # Penalties for disputes
        score -= (self.disputes_filed * 2)  # -2 per dispute filed
        score -= (self.disputes_against * 3)  # -3 per dispute against (lost)
        
        # Bonus for verified email (if email is verified, Django's is_active or custom field)
        if self.is_active and self.email:
            # Check if email is verified (you can add email_verified field if needed)
            score += 1
        
        # Rating impact on trust score
        from orders.models import GiftCardTransactionRating
        ratings = GiftCardTransactionRating.objects.filter(
            rated_user=self,
            is_visible=True
        )
        
        for rating in ratings:
            if rating.rating == 5:
                score += 2  # Excellent rating
            elif rating.rating == 4:
                score += 1  # Good rating
            elif rating.rating == 3:
                score += 0  # Average rating (neutral)
            elif rating.rating == 2:
                score -= 1  # Poor rating
            elif rating.rating == 1:
                score -= 2  # Very poor rating
        
        return max(score, -10)  # Minimum score of -10
    
    def get_effective_trust_score(self):
        """Get trust score (override if set, otherwise calculated)"""
        if self.trust_score_override is not None:
            return self.trust_score_override
        return self.calculate_trust_score()
    
    def get_max_listings_allowed(self):
        """Get maximum number of active listings allowed based on trust score and successful trades"""
        score = self.get_effective_trust_score()
        
        if score < 0:
            return 0  # Cannot create listings
        
        # After 3 successful trades, limit increases to 5 listings
        if self.successful_trades >= 3:
            return 5
        
        # New users (trust_score < 3): Max 1 active listing
        if score < 3:
            return 1
        
        # Trust score 3-10: Max 5 active listings
        if score <= 10:
            return 5
        
        # Trust score > 10: Unlimited
        return None
    
    def can_create_listing(self):
        """Check if user can create a new listing"""
        max_allowed = self.get_max_listings_allowed()
        if max_allowed is None:
            return True
        
        # Count active listings
        from orders.models import GiftCardListing
        active_count = GiftCardListing.objects.filter(
            seller=self,
            status='active'
        ).count()
        
        return active_count < max_allowed
    
    def get_max_gift_card_value_cedis(self):
        """Get maximum gift card value in cedis allowed based on trust score"""
        score = self.get_effective_trust_score()
        
        # New users (trust_score < 3): Cannot list gift cards above 500 cedis
        if score < 3:
            return 500
        
        # Users with trust_score >= 3: No limit
        return None
    
    def update_trust_score(self):
        """Recalculate and save trust score"""
        self.trust_score = self.calculate_trust_score()
        self.save(update_fields=['trust_score'])
    
    def increment_successful_trade(self):
        """Increment successful trades and update trust score"""
        self.successful_trades += 1
        self.update_trust_score()
    
    def increment_dispute_filed(self):
        """Increment disputes filed and update trust score"""
        self.disputes_filed += 1
        self.update_trust_score()
    
    def increment_dispute_against(self):
        """Increment disputes against and update trust score"""
        self.disputes_against += 1
        self.update_trust_score()
    
    def apply_fraud_penalty(self):
        """Apply -5 penalty for fraudulent activity"""
        # We'll manually adjust trust_score for fraud
        self.trust_score = max(self.trust_score - 5, -10)
        self.save(update_fields=['trust_score'])


class OTP(models.Model):
    """
    Model to store OTPs for 2FA authentication.
    OTPs are hashed before storage for security.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp_hash = models.CharField(max_length=255, help_text="Hashed OTP")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0, help_text="Number of verification attempts")
    
    class Meta:
        db_table = 'otps'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_used', 'expires_at']),
        ]
    
    def __str__(self):
        return f"OTP for {self.user.email} - {self.created_at}"
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a random 6-digit OTP"""
        return f"{secrets.randbelow(900000) + 100000:06d}"
    
    @staticmethod
    def hash_otp(otp: str) -> str:
        """Hash OTP using SHA256"""
        return hashlib.sha256(otp.encode()).hexdigest()
    
    @classmethod
    def create_otp(cls, user, expiration_minutes=5):
        """Create a new OTP for a user"""
        # Only invalidate OTPs that are truly expired or very old (older than 10 minutes)
        # This allows users to still use their current OTP if they request a resend by mistake
        cutoff_time = timezone.now() - timedelta(minutes=10)
        cls.objects.filter(
            user=user, 
            is_used=False, 
            created_at__lt=cutoff_time  # Only invalidate old OTPs
        ).update(is_used=True)
        
        # Generate new OTP - call static methods directly on the class
        # Static methods can be called on the class or via cls
        otp = OTP.generate_otp()
        otp_hash = OTP.hash_otp(otp)
        
        # Create OTP record
        otp_obj = cls.objects.create(
            user=user,
            otp_hash=otp_hash,
            expires_at=timezone.now() + timedelta(minutes=expiration_minutes)
        )
        
        return otp, otp_obj
    
    def verify_otp(self, otp: str) -> bool:
        """Verify if the provided OTP matches the stored hash"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Clean the OTP input (remove whitespace, ensure it's a string, remove any non-digit characters)
        otp = str(otp).strip()
        # Remove any non-digit characters (in case of formatting)
        otp = ''.join(filter(str.isdigit, otp))
        
        # Ensure OTP is exactly 6 digits
        if len(otp) != 6:
            logger.warning(f"OTP {self.id} verification failed: OTP length is {len(otp)}, expected 6")
            return False
        
        if self.is_used:
            logger.warning(f"OTP {self.id} already used")
            return False
        
        if timezone.now() > self.expires_at:
            logger.warning(f"OTP {self.id} expired. Now: {timezone.now()}, Expires: {self.expires_at}")
            return False
        
        if self.attempts >= 5:  # Max 5 attempts
            logger.warning(f"OTP {self.id} exceeded max attempts: {self.attempts}")
            return False
        
        self.attempts += 1
        self.save(update_fields=['attempts'])
        
        # Hash the provided OTP
        otp_hash = self.hash_otp(otp)
        
        # Debug logging - show first 20 chars of hash for comparison
        print(f"[OTP MODEL] OTP {self.id}: provided_otp='{otp}', provided_hash='{otp_hash[:20]}...', stored_hash='{self.otp_hash[:20]}...'")
        print(f"[OTP MODEL] Full provided hash: {otp_hash}")
        print(f"[OTP MODEL] Full stored hash: {self.otp_hash}")
        print(f"[OTP MODEL] Hashes match: {otp_hash == self.otp_hash}")
        logger.info(f"OTP verification for OTP {self.id}: provided_otp='{otp}', provided_hash='{otp_hash[:20]}...', stored_hash='{self.otp_hash[:20]}...', match={otp_hash == self.otp_hash}")
        
        if otp_hash == self.otp_hash:
            self.is_used = True
            self.save(update_fields=['is_used'])
            logger.info(f"OTP {self.id} verified successfully")
            return True
        
        logger.warning(f"OTP {self.id} hash mismatch. Attempt {self.attempts}/5. Provided hash: {otp_hash[:20]}..., Stored hash: {self.otp_hash[:20]}...")
        return False
    
    def is_expired(self) -> bool:
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at


class UserDevice(models.Model):
    """
    Model to track user devices for security and fraud prevention.
    Stores device fingerprint information (IP, user agent).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    ip_address = models.GenericIPAddressField(help_text="IP address of the device")
    user_agent = models.TextField(help_text="Browser/device user agent string")
    device_fingerprint = models.CharField(max_length=64, db_index=True, help_text="Hash of IP + user agent for quick lookup")
    is_active = models.BooleanField(default=True, help_text="Whether this device session is active")
    first_seen = models.DateTimeField(auto_now_add=True, help_text="When this device was first seen")
    last_seen = models.DateTimeField(auto_now=True, help_text="When this device was last seen")
    location = models.CharField(max_length=255, blank=True, null=True, help_text="Approximate location (optional)")
    
    class Meta:
        db_table = 'user_devices'
        unique_together = ['user', 'device_fingerprint']
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_fingerprint']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.ip_address} ({self.last_seen})"
    
    @staticmethod
    def generate_fingerprint(ip_address: str, user_agent: str) -> str:
        """Generate a hash fingerprint from IP and user agent"""
        combined = f"{ip_address}:{user_agent}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    @classmethod
    def get_or_create_device(cls, user, ip_address: str, user_agent: str):
        """Get existing device or create a new one"""
        fingerprint = cls.generate_fingerprint(ip_address, user_agent)
        device, created = cls.objects.get_or_create(
            user=user,
            device_fingerprint=fingerprint,
            defaults={
                'ip_address': ip_address,
                'user_agent': user_agent,
                'is_active': True,
            }
        )
        if not created:
            # Update last_seen and ensure it's active
            device.last_seen = timezone.now()
            device.is_active = True
            device.save(update_fields=['last_seen', 'is_active'])
        return device, created


class SecurityLog(models.Model):
    """
    Model to log security events (failed logins, new device logins, etc.)
    """
    EVENT_TYPE_CHOICES = [
        ('failed_login', 'Failed Login Attempt'),
        ('successful_login', 'Successful Login'),
        ('new_device', 'New Device Login'),
        ('device_revoked', 'Device Session Revoked'),
        ('password_change', 'Password Change'),
        ('two_factor_toggle', 'Two-Factor Authentication Toggle'),
        ('account_deactivated', 'Account Deactivated'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('email_verified', 'Email Verified'),
        ('phone_verified', 'Phone Verified'),
        ('ip_banned', 'IP Address Banned'),
        ('withdrawal_request', 'Withdrawal Request'),
        ('gift_card_listed', 'Gift Card Listed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_logs', null=True, blank=True, help_text="User associated with the event (null for failed logins)")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    ip_address = models.GenericIPAddressField(help_text="IP address where the event occurred")
    user_agent = models.TextField(blank=True, null=True, help_text="User agent string")
    details = models.JSONField(default=dict, blank=True, help_text="Additional event details")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else "Unknown"
        return f"{self.event_type} - {user_str} - {self.created_at}"


class BannedIP(models.Model):
    """
    Model to store banned IP addresses for security
    """
    ip_address = models.GenericIPAddressField(unique=True, db_index=True, help_text="Banned IP address")
    reason = models.TextField(help_text="Reason for banning this IP")
    banned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='banned_ips',
        help_text="Admin who banned this IP"
    )
    banned_at = models.DateTimeField(auto_now_add=True, help_text="When this IP was banned")
    is_active = models.BooleanField(default=True, help_text="Whether this ban is currently active")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiration date for temporary bans")
    notes = models.TextField(blank=True, help_text="Additional notes about this ban")
    
    class Meta:
        db_table = 'banned_ips'
        ordering = ['-banned_at']
        verbose_name = 'Banned IP Address'
        verbose_name_plural = 'Banned IP Addresses'
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['is_active', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.ip_address} - Banned at {self.banned_at}"
    
    def is_banned(self):
        """Check if IP is currently banned"""
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            self.is_active = False
            self.save(update_fields=['is_active'])
            return False
        return True
    
    @classmethod
    def is_ip_banned(cls, ip_address):
        """Check if an IP address is banned"""
        banned = cls.objects.filter(
            ip_address=ip_address,
            is_active=True
        ).first()
        if banned:
            return banned.is_banned()
        return False

