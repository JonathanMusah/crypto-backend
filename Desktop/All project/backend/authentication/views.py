from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.utils import timezone
import logging
from django_ratelimit.decorators import ratelimit
from .models import User, OTP, UserDevice, SecurityLog
from .serializers import (
    UserSerializer, 
    RegisterSerializer, 
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordChangeSerializer,
    EmailValidationSerializer,
    PhoneValidationSerializer,
    OTPVerificationSerializer,
    OTPResendSerializer,
    UserDeviceSerializer,
    SecurityLogSerializer
)
from notifications.utils import create_notification
from django.core.cache import cache

logger = logging.getLogger(__name__)
import re


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
    return request.META.get('HTTP_USER_AGENT', '') or ''


class AuthViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'kyc_status', 'is_active', 'is_staff']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone']
    ordering_fields = ['created_at', 'email', 'username']
    ordering = ['-created_at']
    
    def get_permissions(self):
        # Public actions that don't require authentication
        public_actions = ['register', 'login', 'password_reset_request', 'password_reset_confirm', 
                         'validate_email', 'validate_phone', 'verify_otp', 'resend_otp']
        
        if self.action in public_actions:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_authenticators(self):
        """Disable authentication for public endpoints"""
        public_actions = ['register', 'login', 'password_reset_request', 'password_reset_confirm', 
                         'validate_email', 'validate_phone', 'verify_otp', 'resend_otp']
        
        action = getattr(self, 'action', None)
        if action in public_actions:
            return []  # No authentication required
        return super().get_authenticators()
    

    # @ratelimit(key='ip', rate='5/m', block=True)  # Temporarily disabled for debugging
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """Register a new user and return JWT tokens - DEBUG MODE"""
        try:
            logger.info(f"[DEBUG] Registration attempt from IP: {request.META.get('REMOTE_ADDR')}")
            logger.info(f"[DEBUG] Registration data: {request.data}")
            
            # Basic validation first
            if not request.data.get('email'):
                return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('password'):
                return Response({'error': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)
            if not request.data.get('password2'):
                return Response({'error': 'Password confirmation is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = RegisterSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    logger.info(f"[DEBUG] Serializer validation passed")
                    user = serializer.save()
                    logger.info(f"[DEBUG] User created: {user.email}")
                    
                    # Skip wallet creation for now to isolate issue
                    # try:
                    #     from wallets.models import Wallet
                    #     wallet = Wallet.objects.create(user=user)
                    #     logger.info(f"Wallet created for user: {user.email}")
                    # except Exception as wallet_error:
                    #     logger.error(f"Failed to create wallet: {str(wallet_error)}", exc_info=True)
                    
                    # Generate tokens
                    refresh = RefreshToken.for_user(user)
                    logger.info(f"[DEBUG] Tokens generated for user: {user.email}")
                    
                    # Update user's last_seen immediately when they register (they're logged in)
                    user.last_seen = timezone.now()
                    user.save(update_fields=['last_seen'])
                    
                    logger.info(f"[DEBUG] User registered successfully: {user.email}")
                    
                    response = Response({
                        'message': 'User registered successfully',
                        'user': UserSerializer(user).data,
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                    }, status=status.HTTP_201_CREATED)
                    
                    # Set httpOnly cookies
                    response.set_cookie(
                        key='refresh_token',
                        value=str(refresh),
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        max_age=7*24*60*60  # 7 days
                    )
                    response.set_cookie(
                        key='access_token',
                        value=str(refresh.access_token),
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        max_age=60*60  # 1 hour
                    )
                    
                    return response
                except Exception as e:
                    logger.error(f"[DEBUG] Error during user creation: {str(e)}", exc_info=True)
                    return Response(
                        {'error': f'Registration failed: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                logger.warning(f"[DEBUG] Registration validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"[DEBUG] Unexpected error in registration: {str(e)}", exc_info=True)
            return Response(
                {'error': f'An unexpected error occurred during registration: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @ratelimit(key='ip', rate='10/m', block=False)
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """
        Login user - OTP DISABLED FOR TESTING
        Returns JWT tokens directly after password verification
        """
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                logger.warning(f"Login validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = authenticate(
                    username=serializer.validated_data['email'],
                    password=serializer.validated_data['password']
                )
            except Exception as auth_error:
                logger.error(f"Authentication error: {str(auth_error)}", exc_info=True)
                return Response(
                    {'error': 'Authentication service error. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if user and user.is_active:
                # OTP DISABLED - Generate tokens directly
                try:
                    refresh = RefreshToken.for_user(user)
                    
                    # Update user's last_seen
                    user.last_seen = timezone.now()
                    user.save(update_fields=['last_seen'])
                    
                    logger.info(f"User logged in successfully: {user.email}")
                    
                    response = Response({
                        'message': 'Login successful',
                        'user': UserSerializer(user).data,
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                    }, status=status.HTTP_200_OK)
                    
                    # Set httpOnly cookies
                    response.set_cookie(
                        key='refresh_token',
                        value=str(refresh),
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        max_age=7*24*60*60  # 7 days
                    )
                    response.set_cookie(
                        key='access_token',
                        value=str(refresh.access_token),
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        max_age=60*60  # 1 hour
                    )
                    
                    return response
                except Exception as e:
                    logger.error(f"Failed to generate tokens for user {user.email}: {str(e)}", exc_info=True)
                    return Response(
                        {'error': 'Failed to generate authentication tokens. Please try again.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # User doesn't exist or is inactive
                email = serializer.validated_data.get('email', 'unknown')
                logger.warning(f"Login failed for user: {email}")
                
                # Log failed login attempt
                try:
                    ip_address = get_client_ip(request)
                    user_agent = get_user_agent(request)
                    user_agent_str = user_agent if user_agent else ''
                    SecurityLog.objects.create(
                        user=None,
                        event_type='failed_login',
                        ip_address=ip_address,
                        user_agent=user_agent_str,
                        details={
                            'email': email,
                            'message': 'Failed login attempt'
                        }
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log security event: {str(log_error)}", exc_info=True)
                
                return Response(
                    {'error': 'Invalid credentials or account is inactive'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except Exception as e:
            logger.error(f"Unexpected error in login: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout user by blacklisting refresh token, clearing cookies, and marking as offline"""
        try:
            user = request.user
            
            # Mark user as offline by clearing last_seen
            if user.is_authenticated:
                # Set last_seen to None to immediately mark as offline
                user.last_seen = None
                user.save(update_fields=['last_seen'])
                
                # Clear cache entry for last_seen_update
                cache_key = f'last_seen_update_{user.id}'
                cache.delete(cache_key)
                
                logger.info(f"User {user.email} logged out and marked as offline")
            
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            response = Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
            
            # Clear cookies
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            
            return response
        except Exception as e:
            logger.error(f"Error in logout: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Invalid token or already logged out'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def refresh(self, request):
        """Refresh access token using refresh token from cookie"""
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            refresh = RefreshToken(refresh_token)
            
            response = Response({
                'message': 'Token refreshed successfully'
            }, status=status.HTTP_200_OK)
            
            # Update access token cookie
            response.set_cookie(
                key='access_token',
                value=str(refresh.access_token),
                httponly=True,
                secure=True,
                samesite='Lax',
                max_age=60*60
            )
            
            return response
        except Exception as e:
            return Response(
                {'error': 'Invalid or expired refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    @action(detail=False, methods=['get', 'patch', 'put'])
    def me(self, request):
        """Get or update current authenticated user details"""
        if request.method == 'GET':
            serializer = UserSerializer(request.user)
            return Response(serializer.data)
        else:
            # PATCH/PUT - Update user profile
            serializer = UserSerializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def listing_limits(self, request):
        """Get current user's listing limits and status"""
        from orders.models import GiftCardListing
        
        user = request.user
        trust_score = user.get_effective_trust_score()
        max_listings = user.get_max_listings_allowed()
        max_gift_card_value = user.get_max_gift_card_value_cedis()
        active_listings_count = GiftCardListing.objects.filter(
            seller=user,
            status='active'
        ).count()
        can_create = user.can_create_listing()
        
        return Response({
            'trust_score': trust_score,
            'successful_trades': user.successful_trades,
            'max_listings_allowed': max_listings,
            'active_listings_count': active_listings_count,
            'can_create_listing': can_create,
            'max_gift_card_value_cedis': max_gift_card_value,
            'listing_limit_reached': not can_create and max_listings is not None,
            'limit_message': self._get_limit_message(user, max_listings, active_listings_count, max_gift_card_value)
        })
    
    def _get_limit_message(self, user, max_listings, active_count, max_value):
        """Generate a user-friendly message about listing limits"""
        trust_score = user.get_effective_trust_score()
        
        if max_listings == 0:
            return "You cannot create listings. Your trust score is too low. Please complete some successful trades to increase your trust score."
        
        if max_listings == 1:
            if active_count >= max_listings:
                return f"You have reached your listing limit (1/1 active listing). Complete 3 successful trades to increase your limit to 5 listings."
            else:
                return f"New sellers can create up to 1 active listing. Complete 3 successful trades to increase your limit to 5 listings. Max gift card value: {max_value} cedis."
        
        if max_listings == 5:
            if active_count >= max_listings:
                return f"You have reached your listing limit ({active_count}/5 active listings). Continue building your reputation to unlock unlimited listings."
            else:
                return f"You can create up to 5 active listings ({active_count}/5 used). Continue building your reputation to unlock unlimited listings."
        
        return "You have unlimited listings."

    @ratelimit(key='ip', rate='3/m', block=True)
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def password_reset_request(self, request):
        """Request password reset - send reset link to email"""
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Generate password reset token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Create reset link
                reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
                
                # Send email (configure email settings in production)
                send_mail(
                    subject='Password Reset Request',
                    message=f'Click the link to reset your password: {reset_link}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                return Response({
                    'message': 'Password reset email sent successfully'
                }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                # Return success even if user doesn't exist (security best practice)
                return Response({
                    'message': 'If the email exists, a password reset link has been sent'
                }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def password_reset_confirm(self, request):
        """Confirm password reset with token"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
                user = User.objects.get(pk=uid)
                
                if default_token_generator.check_token(user, serializer.validated_data['token']):
                    user.set_password(serializer.validated_data['new_password'])
                    user.save()
                    
                    return Response({
                        'message': 'Password reset successful'
                    }, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {'error': 'Invalid or expired token'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (User.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'error': 'Invalid reset link'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change password for authenticated user"""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            
            # Verify old password
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'error': 'Current password is incorrect'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response({
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @ratelimit(key='ip', rate='20/m', block=True)
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def validate_email(self, request):
        """Validate email format and check if it's already registered"""
        serializer = EmailValidationSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            # Check if email exists
            exists = User.objects.filter(email=email).exists()
            
            return Response({
                'valid': True,
                'available': not exists,
                'message': 'Email is already registered' if exists else 'Email is available'
            }, status=status.HTTP_200_OK)
        return Response({
            'valid': False,
            'available': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @ratelimit(key='ip', rate='20/m', block=True)
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def validate_phone(self, request):
        """Validate phone number format and check if it's already registered"""
        serializer = PhoneValidationSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            
            # Check if phone exists
            exists = User.objects.filter(phone=phone).exists()
            
            return Response({
                'valid': True,
                'available': not exists,
                'message': 'Phone number is already registered' if exists else 'Phone number is available'
            }, status=status.HTTP_200_OK)
        return Response({
            'valid': False,
            'available': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def complete_onboarding(self, request):
        """Mark onboarding as completed for the current user"""
        user = request.user
        user.onboarding_completed = True
        user.save(update_fields=['onboarding_completed'])
        return Response({
            'message': 'Onboarding completed successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def onboarding_status(self, request):
        """Get onboarding status for the current user"""
        return Response({
            'onboarding_completed': request.user.onboarding_completed,
            'user': UserSerializer(request.user).data
        }, status=status.HTTP_200_OK)

    # Temporarily disabled rate limiting to debug OTP verification
    # @ratelimit(key='ip', rate='10/m', block=False)
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='verify-otp')
    def verify_otp(self, request):
        """
        Verify OTP and complete login - Step 2: Verify OTP and create session.
        """
        print("=" * 80)
        print("OTP VERIFICATION REQUEST RECEIVED")
        print(f"Request data: {request.data}")
        print("=" * 80)
        
        serializer = OTPVerificationSerializer(data=request.data)
        print(f"[OTP VERIFY] Serializer is_valid: {serializer.is_valid()}")
        if not serializer.is_valid():
            print(f"[OTP VERIFY] Serializer errors: {serializer.errors}")
        if serializer.is_valid():
            email = serializer.validated_data['email']
            # The serializer already validates and cleans the OTP, so use it directly
            otp = serializer.validated_data['otp']
            
            print(f"[OTP VERIFY] Email: {email}, OTP: {otp}, Length: {len(otp)}")
            logger.info(f"OTP verification request for {email}, OTP received: '{otp}' (length: {len(otp)})")
            
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Invalid email or account is inactive'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Find the most recent unused, non-expired OTP for this user
            # Use __gte (greater than or equal) to be slightly more lenient with timing
            now = timezone.now()
            otp_obj = OTP.objects.filter(
                user=user,
                is_used=False,
                expires_at__gte=now  # Changed to __gte to include OTPs that expire exactly at now
            ).order_by('-created_at').first()
            
            if not otp_obj:
                # Check if there are any OTPs (used or expired) for debugging
                all_otps = OTP.objects.filter(user=user).order_by('-created_at')[:5]
                print(f"[OTP VERIFY] No valid OTP found for user {email}. Current time: {now}")
                logger.warning(f"No valid OTP found for user {email}. Current time: {now}")
                if all_otps.exists():
                    print(f"[OTP VERIFY] Found {all_otps.count()} OTP(s) for user:")
                    for otp_item in all_otps:
                        print(f"  OTP {otp_item.id}: is_used={otp_item.is_used}, expires_at={otp_item.expires_at}, attempts={otp_item.attempts}, created_at={otp_item.created_at}")
                        logger.warning(f"  OTP {otp_item.id}: is_used={otp_item.is_used}, expires_at={otp_item.expires_at}, attempts={otp_item.attempts}")
                else:
                    print(f"[OTP VERIFY] No OTPs found at all for user {email}")
                
                return Response(
                    {'error': 'No valid verification code found. Please request a new code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Log OTP details for debugging
            print(f"[OTP VERIFY] Found OTP object: ID={otp_obj.id}, created_at={otp_obj.created_at}, expires_at={otp_obj.expires_at}, attempts={otp_obj.attempts}, is_used={otp_obj.is_used}")
            logger.info(f"Found OTP for user {email}: ID={otp_obj.id}, expires_at={otp_obj.expires_at}, attempts={otp_obj.attempts}, is_used={otp_obj.is_used}")
            
            # Log verification attempt
            logger.info(f"Verifying OTP for user {email}, OTP object ID: {otp_obj.id}, attempts: {otp_obj.attempts}, expires_at: {otp_obj.expires_at}")
            
            # IMPORTANT: We cannot retrieve the original OTP from the hash, but we can verify the hash
            # The OTP that was sent in the email should match what the user enters
            print(f"[OTP VERIFY] User entered OTP: '{otp}'")
            print(f"[OTP VERIFY] NOTE: The OTP sent in email should match what you enter. Check the email/console for the exact code.")
            
            # Check OTP status before verification
            if otp_obj.is_used:
                logger.warning(f"OTP {otp_obj.id} was already used")
                return Response(
                    {'error': 'This verification code has already been used. Please request a new code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if timezone.now() > otp_obj.expires_at:
                logger.warning(f"OTP {otp_obj.id} has expired. Current time: {timezone.now()}, Expires: {otp_obj.expires_at}")
                return Response(
                    {'error': 'This verification code has expired. Please request a new code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if otp_obj.attempts >= 5:
                logger.warning(f"OTP {otp_obj.id} exceeded max attempts: {otp_obj.attempts}")
                return Response(
                    {'error': 'Too many failed attempts. Please request a new verification code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify OTP
            print(f"[OTP VERIFY] Attempting verification - OTP: {otp}, OTP Object ID: {otp_obj.id}")
            print(f"[OTP VERIFY] Stored hash (first 20 chars): {otp_obj.otp_hash[:20]}...")
            logger.info(f"Attempting to verify OTP for user {email}. OTP provided: {otp}, OTP object ID: {otp_obj.id}")
            is_valid = otp_obj.verify_otp(otp)
            print(f"[OTP VERIFY] Verification result: {is_valid}")
            logger.info(f"OTP verification result for user {email}: {is_valid}")
            
            if not is_valid:
                # Refresh the object to get updated attempts count
                otp_obj.refresh_from_db()
                remaining_attempts = max(0, 5 - otp_obj.attempts)
                print(f"[OTP VERIFY] Verification FAILED for user {email}. Remaining attempts: {remaining_attempts}")
                logger.warning(f"OTP verification failed for user {email}. Remaining attempts: {remaining_attempts}")
                return Response(
                    {'error': f'Invalid verification code. You have {remaining_attempts} attempt(s) remaining.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # OTP verified - complete login
            print(f"[OTP VERIFY] OTP verified successfully! Creating tokens...")
            
            # Mark email as verified when OTP is successfully verified during login
            if not user.email_verified:
                user.email_verified = True
                user.email_verified_at = timezone.now()
                user.save(update_fields=['email_verified', 'email_verified_at'])
                print(f"[OTP VERIFY] Email marked as verified for {user.email}")
                logger.info(f"Email verified for user {user.email} via OTP login")
            
            try:
                refresh = RefreshToken.for_user(user)
                print(f"[OTP VERIFY] Refresh token created successfully")
            except Exception as e:
                print(f"[OTP VERIFY] ERROR creating refresh token: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
            
            logger.info(f"User logged in successfully with OTP: {user.email}")
            
            # Update user's last_seen immediately when they log in
            user.last_seen = timezone.now()
            user.save(update_fields=['last_seen'])
            
            # Clear cache to allow immediate status updates
            cache_key = f'last_seen_update_{user.id}'
            cache.delete(cache_key)
            
            # Capture device information
            print(f"[OTP VERIFY] Capturing device information...")
            try:
                ip_address = get_client_ip(request)
                user_agent = get_user_agent(request)
                print(f"[OTP VERIFY] IP: {ip_address}, User Agent: {user_agent[:50]}...")
            except Exception as e:
                print(f"[OTP VERIFY] ERROR getting device info: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
            
            # Get or create device and check if it's new
            print(f"[OTP VERIFY] Getting/creating device...")
            try:
                device, is_new_device = UserDevice.get_or_create_device(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                print(f"[OTP VERIFY] Device: ID={device.id}, is_new={is_new_device}")
            except Exception as e:
                print(f"[OTP VERIFY] ERROR getting/creating device: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
            
            # Log security event - always log successful logins for audit trail
            try:
                if is_new_device:
                    print(f"[OTP VERIFY] New device detected, creating security log and notifications...")
                    # New device detected - log and send notifications
                    SecurityLog.objects.create(
                        user=user,
                        event_type='new_device',
                        ip_address=ip_address,
                        user_agent=user_agent,
                        details={
                            'device_id': device.id,
                            'device_fingerprint': device.device_fingerprint,
                            'message': 'New device logged in.'
                        }
                    )
                    print(f"[OTP VERIFY] Security log created for new device")
                    
                    # Send notifications for new device logins
                    try:
                        create_notification(
                            user=user,
                            notification_type='NEW_DEVICE_LOGIN',
                            title='New Device Login Detected',
                            message=f'A new device ({device.user_agent[:50]}... from {device.ip_address}) has logged into your account. If this was not you, please secure your account immediately.',
                            related_object_type='user_device',
                            related_object_id=device.id,
                        )
                        print(f"[OTP VERIFY] User notification created")
                        
                        # Send email alert for new device login
                        try:
                            send_mail(
                                subject='New Device Login Detected - Security Alert',
                                message=f'''
Hello {user.get_full_name() or user.email},

A new device has logged into your account.

Device Information:
- IP Address: {device.ip_address}
- User Agent: {device.user_agent[:100]}...
- Time: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}

If this was you, you can safely ignore this email.

If you did not log in from this device, please:
1. Change your password immediately
2. Review your account security settings
3. Contact support if you suspect unauthorized access

Best regards,
CryptoGhana Security Team
                                ''',
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[user.email],
                                fail_silently=True,
                            )
                            logger.info(f"New device login email sent to {user.email}")
                        except Exception as e:
                            logger.warning(f"Failed to send new device email to {user.email}: {str(e)}")
                    except Exception as e:
                        print(f"[OTP VERIFY] ERROR creating user notification: {str(e)}")
                        # Don't fail login if notification fails
                    
                    try:
                        create_notification(
                            user=None, # Admin notification
                            notification_type='ADMIN_NEW_DEVICE_ALERT',
                            title='New Device Login Alert',
                            message=f'User {user.email} logged in from a new device ({device.user_agent[:50]}... from {device.ip_address}).',
                            related_object_type='user_device',
                            related_object_id=device.id,
                            is_admin_notification=True
                        )
                        print(f"[OTP VERIFY] Admin notification created")
                    except Exception as e:
                        print(f"[OTP VERIFY] ERROR creating admin notification: {str(e)}")
                        # Don't fail login if notification fails
                else:
                    # Log successful login from known device (no notification to avoid spam)
                    SecurityLog.objects.create(
                        user=user,
                        event_type='successful_login',
                        ip_address=ip_address,
                        user_agent=user_agent,
                        details={
                            'device_id': device.id,
                            'device_fingerprint': device.device_fingerprint,
                            'message': 'Successful login from known device.'
                        }
                    )
                    print(f"[OTP VERIFY] Security log created for successful login")
            except Exception as e:
                print(f"[OTP VERIFY] ERROR creating security log: {str(e)}")
                import traceback
                traceback.print_exc()
                # Don't fail login if logging fails
            
            print(f"[OTP VERIFY] Creating response...")
            try:
                response = Response({
                    'message': 'Login successful',
                    'user': UserSerializer(user).data,
                    'new_device': is_new_device,  # Inform frontend if this is a new device
                }, status=status.HTTP_200_OK)
                print(f"[OTP VERIFY] Response created successfully")
            except Exception as e:
                print(f"[OTP VERIFY] ERROR creating response: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
            
            # Set httpOnly cookies
            print(f"[OTP VERIFY] Setting cookies...")
            try:
                response.set_cookie(
                    key='refresh_token',
                    value=str(refresh),
                    httponly=True,
                    secure=True,
                    samesite='Lax',
                    max_age=7*24*60*60
                )
                response.set_cookie(
                    key='access_token',
                    value=str(refresh.access_token),
                    httponly=True,
                    secure=True,
                    samesite='Lax',
                    max_age=60*60
                )
                print(f"[OTP VERIFY] Cookies set successfully")
            except Exception as e:
                print(f"[OTP VERIFY] ERROR setting cookies: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
            
            print(f"[OTP VERIFY] Returning successful response!")
            return response
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='resend-otp')
    # @ratelimit decorator disabled - using cache-based rate limiting instead (more reliable)
    def resend_otp(self, request):
        """
        Resend OTP with rate limiting (1 resend every 30 seconds per email, 5 per minute per IP).
        """
        import sys
        # Force output immediately - use multiple methods
        sys.stdout.write("\n[RESEND OTP] ========== ENDPOINT CALLED ==========\n")
        sys.stdout.write(f"[RESEND OTP] Request data: {request.data}\n")
        sys.stdout.flush()
        sys.stderr.write("\n[RESEND OTP] ========== ENDPOINT CALLED (stderr) ==========\n")
        sys.stderr.flush()
        print("\n[RESEND OTP] ========== ENDPOINT CALLED ==========")
        print(f"[RESEND OTP] Request data: {request.data}")
        logger.warning("[RESEND OTP] Endpoint called (WARNING level)")
        logger.error("[RESEND OTP] Endpoint called (ERROR level)")
        try:
            serializer = OTPResendSerializer(data=request.data)
            print(f"[RESEND OTP] Serializer valid: {serializer.is_valid()}")
            sys.stdout.flush()
            if not serializer.is_valid():
                print(f"[RESEND OTP] Serializer errors: {serializer.errors}")
                sys.stdout.flush()
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            email = serializer.validated_data['email']
            print(f"[RESEND OTP] Email: {email}")
            sys.stdout.flush()
            
            # Check rate limit per email (30 seconds)
            cache_key = f'otp_resend_{email}'
            cache_value = cache.get(cache_key)
            print(f"[RESEND OTP] Rate limit check - cache_key: {cache_key}, cached: {cache_value}")
            sys.stdout.flush()
            if cache_value:
                print(f"[RESEND OTP] Rate limited - returning 429")
                sys.stdout.flush()
                return Response(
                    {'error': 'Please wait 30 seconds before requesting a new code.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            
            try:
                user = User.objects.get(email=email, is_active=True)
                print(f"[RESEND OTP] User found: {user.email}")
                sys.stdout.flush()
            except User.DoesNotExist:
                print(f"[RESEND OTP] User not found for email: {email}")
                sys.stdout.flush()
                # Don't reveal if user exists (security best practice)
                return Response(
                    {'message': 'If the email exists, a verification code has been sent.'},
                    status=status.HTTP_200_OK
                )
            
            # Generate new OTP
            print(f"[RESEND OTP] Generating OTP for user: {user.email}")
            sys.stdout.flush()
            try:
                otp, otp_obj = OTP.create_otp(user, expiration_minutes=5)
                
                # FORCE UNBUFFERED OUTPUT
                sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
                sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None
                
                # VERY PROMINENT OTP DISPLAY - Use simple format that works everywhere
                import os
                otp_simple = f"\n\n{'='*80}\nOTP CODE FOR {user.email}: {otp}\n{'='*80}\n\n"
                
                # Print to console multiple times with different methods - FORCE IMMEDIATE OUTPUT
                print(otp_simple, flush=True, end='')
                print(otp_simple, file=sys.stdout, flush=True, end='')
                print(otp_simple, file=sys.stderr, flush=True, end='')
                sys.stdout.write(otp_simple)
                sys.stdout.flush()
                sys.stderr.write(otp_simple)
                sys.stderr.flush()
                
                # Also use logger at CRITICAL level
                logger.critical(otp_simple)
                logger.critical(f"OTP CODE: {otp}")
                
                # Print multiple times to ensure visibility
                for i in range(5):
                    print(f"\n!!! OTP CODE FOR {user.email}: {otp} !!!\n", flush=True)
                    sys.stdout.write(f"\n!!! OTP CODE FOR {user.email}: {otp} !!!\n")
                    sys.stdout.flush()
                
                # VERY PROMINENT OTP DISPLAY (formatted version)
                otp_display = f"""
{'#'*80}
{'#'*80}
{'#'*80}
{'#':<79}#
{'#':<10}OTP CODE FOR {user.email:<40}#
{'#':<10}CODE: {otp:<50}#
{'#':<79}#
{'#'*80}
{'#'*80}
{'#'*80}
"""
                # Print formatted version too
                print(otp_display, flush=True)
                sys.stdout.write(otp_display)
                sys.stdout.flush()
                
                # Write to file as backup (in backend directory)
                try:
                    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    otp_file = os.path.join(backend_dir, 'otp_code.txt')
                    with open(otp_file, 'w') as f:
                        f.write(f"{'='*80}\n")
                        f.write(f"OTP CODE FOR {user.email}\n")
                        f.write(f"CODE: {otp}\n")
                        f.write(f"Generated at: {timezone.now()}\n")
                        f.write(f"{'='*80}\n")
                    print(f"\n[RESEND OTP] OTP saved to file: {otp_file}\n")
                    print(f"[RESEND OTP] Check the file: {otp_file} if you don't see the code above\n")
                    sys.stdout.flush()
                except Exception as e:
                    logger.error(f"Failed to write OTP to file: {str(e)}")
                
                # Logger - use all levels
                logger.critical(f"OTP CODE FOR {user.email}: {otp}")
                logger.error(f"OTP CODE FOR {user.email}: {otp}")
                logger.warning(f"OTP CODE FOR {user.email}: {otp}")
                logger.info(f"OTP CODE FOR {user.email}: {otp}")
            except Exception as e:
                logger.error(f"Failed to create OTP for user {user.email}: {str(e)}", exc_info=True)
                return Response(
                    {'error': 'Failed to generate verification code. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Send OTP email
            try:
                # Check if email backend is configured
                email_backend = getattr(settings, 'EMAIL_BACKEND', '')
                
                if 'console' in email_backend:
                    # For console backend, use fail_silently=True to avoid exceptions
                    # The console email backend will print the email to console automatically
                    # But let's print it BEFORE sending so it's definitely visible
                    print("\n" + "!"*60)
                    print(f"!!! OTP CODE FOR {user.email}: {otp} !!!")
                    print("!"*60 + "\n")
                    sys.stdout.flush()
                    
                    send_mail(
                        subject='Your Login Verification Code',
                        message=f'Your verification code is: {otp}\n\nThis code will expire in 5 minutes.\n\nIf you did not request this code, please ignore this email.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                    # The console backend should have already printed the email above
                    # But let's also explicitly print it again
                    print("\n" + "!"*60)
                    print(f"!!! OTP CODE FOR {user.email}: {otp} !!!")
                    print("!"*60 + "\n")
                    sys.stdout.flush()
                    logger.warning(f"OTP CODE: {otp} for {user.email}")
                    logger.error(f"OTP CODE: {otp} for {user.email}")  # ERROR level to ensure visibility
                else:
                    # For real SMTP, fail_silently=False to catch errors
                    send_mail(
                        subject='Your Login Verification Code',
                        message=f'Your verification code is: {otp}\n\nThis code will expire in 5 minutes.\n\nIf you did not request this code, please ignore this email.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    logger.info(f"OTP resent to {user.email}")
                    # Also print to console even for SMTP in development
                    print(f"\n[SMTP] OTP sent via email to {user.email}: {otp}\n")
                
                # Set rate limit cache (30 seconds)
                cache.set(cache_key, True, 30)
                
                # In DEBUG mode, include OTP in response for development convenience
                response_data = {
                    'message': 'Verification code sent to your email',
                    'email': user.email
                }
                if settings.DEBUG:
                    response_data['otp_code'] = otp
                    response_data['debug_note'] = 'OTP shown in DEBUG mode only. Check backend/otp_code.txt file for production.'
                
                return Response(response_data, status=status.HTTP_200_OK)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send OTP email to {user.email}: {error_msg}", exc_info=True)
                otp_obj.delete()  # Clean up if email fails
                
                # Provide more helpful error message
                if 'smtp' in error_msg.lower() or 'connection' in error_msg.lower():
                    error_message = 'Email server connection failed. Please check your email configuration.'
                elif 'authentication' in error_msg.lower() or 'credentials' in error_msg.lower():
                    error_message = 'Email authentication failed. Please check your email credentials.'
                else:
                    error_message = f'Failed to send verification code: {error_msg}'
                
                return Response(
                    {'error': error_message},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Unexpected error in resend_otp: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @ratelimit(key='ip', rate='10/m', block=True)
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def verify_email(self, request):
        """Verify user's email using a token (sent via email)"""
        token = request.data.get('token')
        if not token:
            return Response(
                {'error': 'Verification token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # For now, we'll use a simple approach: if user is authenticated and requests verification,
            # we'll verify their email. In production, you'd validate a token sent via email.
            # TODO: Implement proper token-based email verification
            user = request.user
            if user.email_verified:
                return Response(
                    {'message': 'Email is already verified'},
                    status=status.HTTP_200_OK
                )
            
            user.email_verified = True
            user.save(update_fields=['email_verified'])
            
            # Log security event
            SecurityLog.objects.create(
                user=user,
                event_type='email_verified',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                details={'email': user.email}
            )
            
            return Response({
                'message': 'Email verified successfully',
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Email verification failed for {request.user.email}: {str(e)}")
            return Response(
                {'error': 'Email verification failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @ratelimit(key='ip', rate='10/m', block=True)
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def send_phone_otp(self, request):
        """Send OTP to user's phone for verification (placeholder for SMS integration)"""
        user = request.user
        if not user.phone:
            return Response(
                {'error': 'Phone number is not set. Please add a phone number first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.phone_verified:
            return Response(
                {'message': 'Phone is already verified'},
                status=status.HTTP_200_OK
            )
        
        # TODO: Integrate with SMS service (e.g., Twilio, AWS SNS)
        # For now, return a placeholder response
        return Response({
            'message': 'Phone verification OTP will be sent (SMS integration pending)',
            'phone': user.phone
        }, status=status.HTTP_200_OK)
    
    @ratelimit(key='ip', rate='10/m', block=True)
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def verify_phone(self, request):
        """Verify user's phone using OTP"""
        otp = request.data.get('otp')
        if not otp:
            return Response(
                {'error': 'OTP is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        if not user.phone:
            return Response(
                {'error': 'Phone number is not set'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # TODO: Verify OTP with SMS service
        # For now, accept any 6-digit OTP as valid (for testing)
        if len(str(otp)) == 6 and str(otp).isdigit():
            user.phone_verified = True
            user.save(update_fields=['phone_verified'])
            
            # Log security event
            SecurityLog.objects.create(
                user=user,
                event_type='phone_verified',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                details={'phone': user.phone}
            )
            
            return Response({
                'message': 'Phone verified successfully',
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Invalid OTP format'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def test_console(self, request):
        """Test endpoint to verify console output works - for debugging OTP display"""
        import sys
        import os
        from pathlib import Path
        
        test_message = "\n\n" + "="*80 + "\nTEST CONSOLE OUTPUT - If you see this, console output works!\n" + "="*80 + "\n\n"
        
        # Try multiple output methods
        print(test_message, flush=True)
        sys.stdout.write(test_message)
        sys.stdout.flush()
        sys.stderr.write(test_message)
        sys.stderr.flush()
        logger.critical(test_message)
        
        # Check OTP file
        backend_dir = Path(__file__).parent.parent
        otp_file = backend_dir / 'otp_code.txt'
        otp_file_exists = otp_file.exists()
        otp_content = None
        
        if otp_file_exists:
            try:
                with open(otp_file, 'r') as f:
                    otp_content = f.read()
            except Exception as e:
                otp_content = f"Error reading file: {str(e)}"
        
        return Response({
            'message': 'Check your Django server console - you should see a test message',
            'console_output': 'If you see this response, check the terminal where Django is running',
            'otp_file_path': str(otp_file),
            'otp_file_exists': otp_file_exists,
            'otp_file_content': otp_content if otp_file_exists else 'No OTP file found yet. Log in or resend OTP to generate one.',
            'instructions': [
                '1. Check the Django server console (where you ran "python manage.py runserver")',
                f'2. Check the OTP file at: {otp_file}',
                '3. Run: python check_otp.py (in the backend directory)',
                '4. Make sure you are looking at the correct terminal window'
            ]
        })