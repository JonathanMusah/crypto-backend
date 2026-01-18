"""
Scam detection and content filtering for messages
"""
import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# Forbidden patterns
FORBIDDEN_PATTERNS = {
    'phone_number': [
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US format
        r'\b\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',  # International
        r'\b0\d{9}\b',  # Ghana format
        r'\b\+233\d{9}\b',  # Ghana international
    ],
    'whatsapp': [
        r'whatsapp',
        r'wa\.me',
        r'wa\.link',
        r'chat\.whatsapp',
    ],
    'telegram': [
        r'telegram',
        r'@\w+',  # Telegram username
        r't\.me/',
        r'telegram\.me',
    ],
    'momo_number': [
        r'momo',
        r'mobile\s*money',
        r'mtn\s*momo',
        r'vodafone\s*cash',
        r'airteltigo\s*money',
    ],
    'crypto_wallet': [
        r'\b0x[a-fA-F0-9]{40}\b',  # Ethereum
        r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b',  # Bitcoin
        r'\bT[A-Za-z1-9]{33}\b',  # Tron
        r'wallet\s*address',
        r'send\s*(to|at)\s*(my|this)\s*wallet',
    ],
    'email': [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ],
    'external_link': [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        r'www\.\w+\.\w+',
        r'bit\.ly/\w+',
        r'tinyurl\.com/\w+',
    ],
}

# Scam patterns (high risk)
SCAM_PATTERNS = {
    'deal_outside': [
        r'deal\s*(outside|off)\s*(the\s*)?platform',
        r'transaction\s*(outside|off)\s*(the\s*)?platform',
        r'pay\s*(outside|off)\s*(the\s*)?platform',
        r'let\'?s\s*(do|make)\s*(it|this)\s*(outside|off)',
        r'we\s*can\s*(do|make)\s*(it|this)\s*(outside|off)',
    ],
    'pay_first': [
        r'pay\s*(now|first)',
        r'send\s*(money|payment)\s*(now|first)',
        r'pay\s*before',
        r'payment\s*(first|before)',
    ],
    'cant_receive_platform': [
        r'can\'?t\s*receive\s*(through|on|via)\s*platform',
        r'platform\s*(doesn\'?t|don\'?t)\s*work',
        r'escrow\s*(doesn\'?t|don\'?t)\s*work',
        r'can\'?t\s*use\s*platform',
    ],
    'move_to_telegram': [
        r'move\s*(to|on)\s*telegram',
        r'contact\s*(me|us)\s*(on|via)\s*telegram',
        r'let\'?s\s*chat\s*(on|via)\s*telegram',
    ],
    'send_to_number': [
        r'send\s*(money|payment)\s*(to|at)\s*(this|my|the)\s*number',
        r'pay\s*(to|at)\s*(this|my|the)\s*number',
    ],
    'discount_outside': [
        r'discount\s*if\s*(we|you)\s*(do|make)\s*(it|this)\s*(outside|off)',
        r'cheaper\s*if\s*(we|you)\s*(do|make)\s*(it|this)\s*(outside|off)',
        r'better\s*price\s*(outside|off)\s*platform',
    ],
    'gift_card_fraud': [
        r'gift\s*card\s*(already|already\s*used|expired)',
        r'card\s*(already|already\s*used|expired)',
        r'code\s*(already|already\s*used|expired)',
        r'you\s*won\'?t\s*need\s*to\s*verify',
        r'trust\s*me',
        r'no\s*need\s*to\s*check',
    ],
    'urgent_payment': [
        r'urgent',
        r'asap',
        r'quickly',
        r'now\s*or\s*never',
        r'limited\s*time',
    ],
}


def detect_forbidden_content(text: str) -> Tuple[bool, List[str]]:
    """
    Detect forbidden content patterns (contact info, external links, etc.)
    Returns: (is_forbidden, detected_patterns)
    """
    text_lower = text.lower()
    detected = []

    for pattern_type, patterns in FORBIDDEN_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected.append(pattern_type)
                break  # Only add each type once

    return len(detected) > 0, detected


def detect_scam_patterns(text: str) -> Tuple[bool, List[str], int]:
    """
    Detect scam patterns in message
    Returns: (is_scam, detected_patterns, risk_score)
    """
    text_lower = text.lower()
    detected = []
    risk_score = 0

    for pattern_type, patterns in SCAM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected.append(pattern_type)
                # Assign risk scores
                if pattern_type in ['deal_outside', 'pay_first', 'cant_receive_platform']:
                    risk_score += 20
                elif pattern_type in ['move_to_telegram', 'send_to_number', 'discount_outside']:
                    risk_score += 15
                elif pattern_type in ['gift_card_fraud', 'urgent_payment']:
                    risk_score += 10
                break  # Only add each type once

    return len(detected) > 0, detected, risk_score


def filter_forbidden_content(text: str) -> str:
    """
    Replace forbidden content with [BLOCKED FOR SECURITY]
    """
    filtered_text = text

    # Replace phone numbers
    for pattern in FORBIDDEN_PATTERNS['phone_number']:
        filtered_text = re.sub(pattern, '[BLOCKED FOR SECURITY]', filtered_text, flags=re.IGNORECASE)

    # Replace email addresses
    for pattern in FORBIDDEN_PATTERNS['email']:
        filtered_text = re.sub(pattern, '[BLOCKED FOR SECURITY]', filtered_text, flags=re.IGNORECASE)

    # Replace crypto wallet addresses
    for pattern in FORBIDDEN_PATTERNS['crypto_wallet']:
        filtered_text = re.sub(pattern, '[BLOCKED FOR SECURITY]', filtered_text, flags=re.IGNORECASE)

    # Replace external links
    for pattern in FORBIDDEN_PATTERNS['external_link']:
        filtered_text = re.sub(pattern, '[BLOCKED FOR SECURITY]', filtered_text, flags=re.IGNORECASE)

    # Replace WhatsApp/Telegram references
    for pattern in FORBIDDEN_PATTERNS['whatsapp'] + FORBIDDEN_PATTERNS['telegram']:
        filtered_text = re.sub(pattern, '[BLOCKED FOR SECURITY]', filtered_text, flags=re.IGNORECASE)

    # Replace MoMo references
    for pattern in FORBIDDEN_PATTERNS['momo_number']:
        filtered_text = re.sub(pattern, '[BLOCKED FOR SECURITY]', filtered_text, flags=re.IGNORECASE)

    return filtered_text


def sanitize_message_content(text: str) -> str:
    """
    Sanitize message content (remove HTML, trim whitespace)
    """
    import html
    # Escape HTML
    text = html.escape(text)
    # Trim whitespace
    text = text.strip()
    # Remove excessive newlines (max 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def analyze_message(text: str) -> Dict:
    """
    Complete message analysis
    Returns analysis dict with all detection results
    """
    original_text = text
    sanitized_text = sanitize_message_content(text)
    
    # Detect forbidden content
    has_forbidden, forbidden_patterns = detect_forbidden_content(sanitized_text)
    
    # Filter forbidden content
    if has_forbidden:
        filtered_text = filter_forbidden_content(sanitized_text)
    else:
        filtered_text = sanitized_text
    
    # Detect scam patterns
    has_scam, scam_patterns, risk_score = detect_scam_patterns(sanitized_text)
    
    return {
        'original_content': original_text,
        'sanitized_content': sanitized_text,
        'filtered_content': filtered_text,
        'has_forbidden': has_forbidden,
        'forbidden_patterns': forbidden_patterns,
        'has_scam': has_scam,
        'scam_patterns': scam_patterns,
        'risk_score': risk_score,
        'was_filtered': has_forbidden,
    }

