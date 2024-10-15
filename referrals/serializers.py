from time import timezone

from rest_framework import serializers

from .models import ReferralCode
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralCode
        fields = ('id', 'code', 'expiration_date', 'user')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    referral_code = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'referral_code')

    def create(self, validated_data):
        referral_code = validated_data.pop('referral_code', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )


        if referral_code:
            try:
                referral = ReferralCode.objects.get(code=referral_code)

                if referral.expiration_date and referral.expiration_date < timezone.now():
                    raise serializers.ValidationError({"referral_code": "Реферальный код просрочен."})
            except ReferralCode.DoesNotExist:
                raise serializers.ValidationError({"referral_code": "Неверный реферальный код."})

        return user


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    pass