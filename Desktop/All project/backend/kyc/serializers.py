from rest_framework import serializers
from .models import KYCVerification


class KYCVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCVerification
        fields = ('id', 'user', 'status', 'document_type', 'document_number', 'first_name', 'last_name', 'date_of_birth', 'address', 'document_front', 'document_back', 'selfie', 'rejection_reason', 'submitted_at', 'reviewed_at')
        read_only_fields = ('id', 'user', 'status', 'rejection_reason', 'reviewed_by', 'submitted_at', 'reviewed_at')


class KYCSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCVerification
        fields = ('document_type', 'document_number', 'first_name', 'last_name', 'date_of_birth', 'address', 'document_front', 'document_back', 'selfie')

