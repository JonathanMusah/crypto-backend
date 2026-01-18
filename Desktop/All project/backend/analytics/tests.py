from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Settings, AnalyticsEvent, UserMetric

User = get_user_model()


class SettingsModelTest(TestCase):
    def setUp(self):
        self.settings = Settings.objects.create(
            live_rate_source='coinmarketcap',
            escrow_percent='2.00',
            support_contacts={'email': 'support@example.com', 'phone': '+1234567890'}
        )

    def test_settings_creation(self):
        """Test that settings are created correctly"""
        self.assertEqual(self.settings.live_rate_source, 'coinmarketcap')
        self.assertEqual(self.settings.escrow_percent, '2.00')
        self.assertEqual(self.settings.support_contacts['email'], 'support@example.com')
        self.assertEqual(self.settings.support_contacts['phone'], '+1234567890')

    def test_settings_str(self):
        """Test settings string representation"""
        self.assertEqual(str(self.settings), 'Platform Settings')


class AnalyticsEventModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.event = AnalyticsEvent.objects.create(
            user=self.user,
            event_type='PAGE_VIEW',
            event_name='Home Page Visit',
            properties={'page': '/', 'referrer': 'google.com'},
            session_id='session123',
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0'
        )

    def test_analytics_event_creation(self):
        """Test that analytics event is created correctly"""
        self.assertEqual(self.event.user, self.user)
        self.assertEqual(self.event.event_type, 'PAGE_VIEW')
        self.assertEqual(self.event.event_name, 'Home Page Visit')
        self.assertEqual(self.event.properties['page'], '/')
        self.assertEqual(self.event.properties['referrer'], 'google.com')
        self.assertEqual(self.event.session_id, 'session123')
        self.assertEqual(self.event.ip_address, '127.0.0.1')
        self.assertEqual(self.event.user_agent, 'Mozilla/5.0')

    def test_analytics_event_str(self):
        """Test analytics event string representation"""
        expected = f"{self.event.event_type} - {self.event.event_name}"
        self.assertEqual(str(self.event), expected)


class UserMetricModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.metrics = UserMetric.objects.create(
            user=self.user,
            total_trades=5,
            total_volume='1.25000000',
            total_profit='0.05000000'
        )

    def test_user_metric_creation(self):
        """Test that user metrics are created correctly"""
        self.assertEqual(self.metrics.user, self.user)
        self.assertEqual(self.metrics.total_trades, 5)
        self.assertEqual(self.metrics.total_volume, '1.25000000')
        self.assertEqual(self.metrics.total_profit, '0.05000000')
        self.assertIsNone(self.metrics.last_trade_at)

    def test_user_metric_str(self):
        """Test user metrics string representation"""
        expected = f"{self.user.email} - Metrics"
        self.assertEqual(str(self.metrics), expected)