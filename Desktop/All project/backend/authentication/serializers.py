from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator
from .models import User, UserDevice, SecurityLog
import re


class UserSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        # Auto-sync KYC status from KYCVerification if it exists
        try:
            from kyc.models import KYCVerification
            kyc_verification = KYCVerification.objects.filter(user=instance).first()
            if kyc_verification:
                # Map KYCVerification status to User.kyc_status
                status_map = {
                    'APPROVED': 'approved',
                    'REJECTED': 'rejected',
                    'PENDING': 'pending',
                    'UNDER_REVIEW': 'pending',
                }
                expected_status = status_map.get(kyc_verification.status, 'pending')
                
                # Sync if different
                if instance.kyc_status != expected_status:
                    instance.kyc_status = expected_status
                    instance.save(update_fields=['kyc_status'])
        except Exception:
            # Silently fail if KYC app not available or other error
            pass
        
        return super().to_representation(instance)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'kyc_status', 'onboarding_completed', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at', 'kyc_status')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label='Confirm Password')
    email = serializers.EmailField(required=True, validators=[EmailValidator()])
    username = serializers.CharField(required=False, allow_blank=True)  # Auto-generated if not provided
    phone = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'phone', 'first_name', 'last_name')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate_phone(self, value):
        if value:
            # Basic phone validation - adjust regex based on your requirements
            phone_regex = re.compile(r'^\+?1?\d{9,15}$')
            if not phone_regex.match(value):
                raise serializers.ValidationError("Invalid phone number format. Use format: +233123456789")
            if User.objects.filter(phone=value).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        # Generate unique username from email if not provided
        if not attrs.get('username'):
            base_username = attrs['email'].split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            attrs['username'] = username
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            phone=validated_data.get('phone', ''),
            first_name=first_name,
            last_name=last_name
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate_email(self, value):
        return value.lower()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True, label='Confirm New Password')

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True, label='Confirm New Password')

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs


class EmailValidationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, validators=[EmailValidator()])

    def validate_email(self, value):
        return value.lower()


class PhoneValidationSerializer(serializers.Serializer):
    phone = serializers.CharField(required=True)

    def validate_phone(self, value):
        # Validate phone format
        phone_regex = re.compile(r'^\+?1?\d{9,15}$')
        if not phone_regex.match(value):
            raise serializers.ValidationError("Invalid phone number format. Use format: +233123456789")
        return value


class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_otp(self, value):
        # Remove any whitespace and ensure it's exactly 6 digits
        value = str(value).strip().replace(' ', '')
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        if len(value) != 6:
            raise serializers.ValidationError("OTP must be exactly 6 digits")
        return value


class OTPResendSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        return value.lower()


class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for user device information"""
    device_info = serializers.SerializerMethodField()
    is_current_device = serializers.SerializerMethodField()
    
    class Meta:
        model = UserDevice
        fields = ('id', 'ip_address', 'user_agent', 'device_info', 'is_active', 'first_seen', 'last_seen', 'location', 'is_current_device')
        read_only_fields = ('id', 'ip_address', 'user_agent', 'first_seen', 'last_seen', 'location', 'device_info', 'is_current_device')
    
    def get_device_info(self, obj):
        """Parse user agent to extract device/browser info"""
        ua = obj.user_agent or ''
        info = {
            'browser': 'Unknown',
            'os': 'Unknown',
            'device': 'Unknown',
        }
        
        # Simple parsing (can be enhanced with user-agents library)
        if 'Chrome' in ua:
            info['browser'] = 'Chrome'
        elif 'Firefox' in ua:
            info['browser'] = 'Firefox'
        elif 'Safari' in ua and 'Chrome' not in ua:
            info['browser'] = 'Safari'
        elif 'Edge' in ua:
            info['browser'] = 'Edge'
        
        if 'Windows' in ua:
            info['os'] = 'Windows'
        elif 'Mac' in ua or 'macOS' in ua:
            info['os'] = 'macOS'
        elif 'Linux' in ua:
            info['os'] = 'Linux'
        elif 'Android' in ua:
            info['os'] = 'Android'
        elif 'iOS' in ua or 'iPhone' in ua or 'iPad' in ua:
            info['os'] = 'iOS'
        
        if 'Mobile' in ua or 'Android' in ua or 'iPhone' in ua:
            info['device'] = 'Mobile'
        elif 'Tablet' in ua or 'iPad' in ua:
            info['device'] = 'Tablet'
        else:
            info['device'] = 'Desktop'
        
        return info
    
    def get_is_current_device(self, obj):
        """Check if this is the current device making the request"""
        request = self.context.get('request')
        if not request:
            return False
        
        current_ip = self._get_client_ip(request)
        current_ua = request.META.get('HTTP_USER_AGENT', '')
        current_fingerprint = UserDevice.generate_fingerprint(current_ip, current_ua)
        
        return obj.device_fingerprint == current_fingerprint
    
    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityLogSerializer(serializers.ModelSerializer):
    """Serializer for security logs"""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = SecurityLog
        fields = ('id', 'user', 'user_email', 'event_type', 'event_type_display', 'ip_address', 'user_agent', 'details', 'created_at')
        read_only_fields = ('id', 'user', 'user_email', 'event_type', 'event_type_display', 'ip_address', 'user_agent', 'details', 'created_at')

