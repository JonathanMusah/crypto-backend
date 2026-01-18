from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.notification = Notification.objects.create(
            user=self.user,
            title='Test Notification',
            message='This is a test notification',
            notification_type='SYSTEM',
            read=False
        )

    def test_notification_creation(self):
        """Test that notification is created correctly"""
        self.assertEqual(self.notification.user, self.user)
        self.assertEqual(self.notification.title, 'Test Notification')
        self.assertEqual(self.notification.message, 'This is a test notification')
        self.assertEqual(self.notification.notification_type, 'SYSTEM')
        self.assertFalse(self.notification.read)

    def test_notification_str(self):
        """Test notification string representation"""
        expected = f"Notification for {self.user.email}: Test Notification"
        self.assertEqual(str(self.notification), expected)

    def test_mark_as_read(self):
        """Test marking notification as read"""
        self.assertFalse(self.notification.read)
        self.notification.mark_as_read()
        self.assertTrue(self.notification.read)

    def test_get_unread_count(self):
        """Test getting unread notification count"""
        # Create another unread notification
        Notification.objects.create(
            user=self.user,
            title='Test Notification 2',
            message='This is another test notification',
            notification_type='SYSTEM',
            read=False
        )
        
        # Create a read notification
        Notification.objects.create(
            user=self.user,
            title='Test Notification 3',
            message='This is a read test notification',
            notification_type='SYSTEM',
            read=True
        )
        
        unread_count = Notification.get_unread_count(self.user)
        self.assertEqual(unread_count, 2)