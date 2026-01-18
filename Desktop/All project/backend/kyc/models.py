from django.db import models
from django.conf import settings


class KYCVerification(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    DOCUMENT_TYPE_CHOICES = [
        ('PASSPORT', 'Passport'),
        ('DRIVER_LICENSE', 'Driver License'),
        ('NATIONAL_ID', 'National ID'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kyc_verification')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    document_number = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    address = models.TextField()
    document_front = models.ImageField(upload_to='kyc/documents/')
    document_back = models.ImageField(upload_to='kyc/documents/', blank=True, null=True)
    selfie = models.ImageField(upload_to='kyc/selfies/')
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_kyc')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'kyc_verifications'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.email} - {self.status}"

