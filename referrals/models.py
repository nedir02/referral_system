from django.contrib.auth.models import User
from django.db import models


class ReferralCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    expiration_date = models.DateTimeField()

    def __str__(self):
        return self.code