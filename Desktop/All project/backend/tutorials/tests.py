from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Tutorial, TutorialProgress

User = get_user_model()


class TutorialModelTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username='author',
            email='author@example.com',
            password='testpass123'
        )
        self.tutorial = Tutorial.objects.create(
            title='Getting Started with Crypto',
            content='This is a tutorial about crypto trading',
            category='beginner',
            slug='getting-started-with-crypto',
            excerpt='Learn the basics of crypto trading',
            order=1,
            is_published=True,
            author=self.author,
            views=100
        )

    def test_tutorial_creation(self):
        """Test that tutorial is created correctly"""
        self.assertEqual(self.tutorial.title, 'Getting Started with Crypto')
        self.assertEqual(self.tutorial.content, 'This is a tutorial about crypto trading')
        self.assertEqual(self.tutorial.category, 'beginner')
        self.assertEqual(self.tutorial.slug, 'getting-started-with-crypto')
        self.assertEqual(self.tutorial.excerpt, 'Learn the basics of crypto trading')
        self.assertEqual(self.tutorial.order, 1)
        self.assertTrue(self.tutorial.is_published)
        self.assertEqual(self.tutorial.author, self.author)
        self.assertEqual(self.tutorial.views, 100)

    def test_tutorial_str(self):
        """Test tutorial string representation"""
        self.assertEqual(str(self.tutorial), 'Getting Started with Crypto')


class TutorialProgressModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.author = User.objects.create_user(
            username='author',
            email='author@example.com',
            password='testpass123'
        )
        self.tutorial = Tutorial.objects.create(
            title='Getting Started with Crypto',
            content='This is a tutorial about crypto trading',
            category='beginner',
            slug='getting-started-with-crypto',
            excerpt='Learn the basics of crypto trading',
            order=1,
            is_published=True,
            author=self.author
        )
        self.progress = TutorialProgress.objects.create(
            user=self.user,
            tutorial=self.tutorial,
            is_completed=False
        )

    def test_tutorial_progress_creation(self):
        """Test that tutorial progress is created correctly"""
        self.assertEqual(self.progress.user, self.user)
        self.assertEqual(self.progress.tutorial, self.tutorial)
        self.assertFalse(self.progress.is_completed)

    def test_tutorial_progress_str(self):
        """Test tutorial progress string representation"""
        expected = f"{self.user.email} - {self.tutorial.title}"
        self.assertEqual(str(self.progress), expected)

    def test_tutorial_progress_completion(self):
        """Test marking tutorial as completed"""
        self.assertFalse(self.progress.is_completed)
        self.assertIsNone(self.progress.completed_at)
        
        # Mark as completed
        from django.utils import timezone
        self.progress.is_completed = True
        self.progress.completed_at = timezone.now()
        self.progress.save()
        
        self.assertTrue(self.progress.is_completed)
        self.assertIsNotNone(self.progress.completed_at)