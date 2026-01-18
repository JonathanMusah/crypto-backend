"""
Security utilities for gift card transactions
"""
import logging
from django.utils import timezone
from datetime import timedelta
from authentication.models import UserDevice, SecurityLog
import hashlib

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def get_user_agent(request):
    """Extract user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')


def generate_device_fingerprint(ip_address, user_agent):
    """Generate a unique hash for a device based on IP and user agent"""
    combined_string = f"{ip_address}-{user_agent}"
    return hashlib.sha256(combined_string.encode('utf-8')).hexdigest()


def calculate_risk_score(user, request):
    """
    Calculates a risk score for a transaction based on various factors.
    Score range: 0-100 (higher = more risk)
    Returns: (risk_score, risk_factors)
    """
    risk_score = 0
    risk_factors = {}

    # 1. User Trust Score (Inverse relationship: lower trust = higher risk)
    user_trust_score = user.get_effective_trust_score()
    # Normalize trust score (e.g., -10 to 10+ range) to a risk component
    # Example: if trust is -10, add 30 risk. If trust is 10, add 0 risk.
    trust_risk = max(0, 10 - user_trust_score) * 1.5  # Max 30 points for very low trust
    risk_score += trust_risk
    risk_factors['user_trust_score'] = {'value': user_trust_score, 'impact': trust_risk}

    # 2. Device Reputation (New device, suspicious activity from device)
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    device_fingerprint = generate_device_fingerprint(ip_address, user_agent)

    device, created = UserDevice.objects.get_or_create(
        user=user,
        device_fingerprint=device_fingerprint,
        defaults={'ip_address': ip_address, 'user_agent': user_agent}
    )

    if created:
        risk_score += 20  # Significant risk for new device
        risk_factors['new_device'] = {'value': True, 'impact': 20}
    else:
        # Check if device has been associated with recent suspicious activity
        recent_suspicious_logs = SecurityLog.objects.filter(
            user=user,
            ip_address=ip_address,
            event_type='suspicious_activity',
            created_at__gt=timezone.now() - timedelta(days=7)
        ).count()
        if recent_suspicious_logs > 0:
            suspicious_impact = min(20, recent_suspicious_logs * 5)  # Max 20 points
            risk_score += suspicious_impact
            risk_factors['suspicious_device_activity'] = {
                'value': recent_suspicious_logs,
                'impact': suspicious_impact
            }
    
    # 3. Account Age (New accounts are higher risk)
    account_age_days = (timezone.now() - user.date_joined).days
    if account_age_days < 7:
        risk_score += 15  # Very new account
        risk_factors['account_age'] = {'value': f"{account_age_days} days", 'impact': 15}
    elif account_age_days < 30:
        risk_score += 5  # Relatively new account
        risk_factors['account_age'] = {'value': f"{account_age_days} days", 'impact': 5}

    # 4. Past Disputes (User's history of disputes)
    # disputes_filed and disputes_against are already on User model
    if user.disputes_filed > 0:
        disputes_filed_impact = min(10, user.disputes_filed * 3)  # Max 10 points
        risk_score += disputes_filed_impact
        risk_factors['past_disputes_filed'] = {
            'value': user.disputes_filed,
            'impact': disputes_filed_impact
        }
    if user.disputes_against > 0:
        disputes_against_impact = min(20, user.disputes_against * 5)  # Max 20 points
        risk_score += disputes_against_impact
        risk_factors['past_disputes_against'] = {
            'value': user.disputes_against,
            'impact': disputes_against_impact
        }

    # 5. Email/Phone Verification Status
    if not user.email_verified:
        risk_score += 10
        risk_factors['email_unverified'] = {'value': True, 'impact': 10}
    if not user.phone_verified:  # Phone is optional, so lower impact
        risk_score += 5
        risk_factors['phone_unverified'] = {'value': True, 'impact': 5}

    # Cap risk score at 100
    final_risk_score = min(100, int(risk_score))
    risk_factors['final_score'] = final_risk_score

    logger.info(
        f"Calculated risk score for user {user.email}: {final_risk_score}. "
        f"Factors: {risk_factors}"
    )
    return final_risk_score, risk_factors
