# core_passport/serializers.py

from rest_framework import serializers
from .models import DigitalPassport 

class PassportMintSerializer(serializers.Serializer):
    imei_serial = serializers.CharField(max_length=50)
    wipe_status = serializers.CharField(max_length=50) 
    wipe_standard = serializers.CharField(max_length=100)
    verification_log = serializers.CharField(required=False, allow_blank=True) 

    def validate_wipe_status(self, value):
        """Custom validation to ensure the wipe was successful."""
        if value != "SUCCESS":
            raise serializers.ValidationError("Wipe process reported failure.")
        return value

    def create(self, validated_data):
        passport = DigitalPassport.objects.create(
            imei_serial=validated_data['imei_serial'],
            is_certified=True,
            wipe_standard=validated_data['wipe_standard']
        )
        return passport