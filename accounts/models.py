from django.db import models
from django.contrib.auth.models import User


class EmailOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_otp")
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.email}"


class PasswordResetOTP(models.Model):
    """Stores a one-time OTP used for the forgot-password reset flow."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="password_reset_otp")
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now=True)  # refreshes on each update_or_create
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Reset OTP for {self.user.username}"