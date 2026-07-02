from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from accounts.models import EmailOTP, PasswordResetOTP
from accounts.utils import generate_otp, send_otp_email
from subscription.models import Subscription, UserSubscription
from django.utils import timezone
from datetime import timedelta

class AccountsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")

    def test_email_otp_creation(self):
        otp = generate_otp()
        otp_obj = EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp=otp,
            is_verified=False
        )
        self.assertEqual(otp_obj.otp, otp)
        self.assertFalse(otp_obj.is_verified)
        self.assertEqual(str(otp_obj), "testuser - test@example.com")

    def test_send_otp_email(self):
        send_otp_email("test@example.com", "123456")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Your OTP Verification Code")
        self.assertIn("123456", mail.outbox[0].body)


class AccountsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Seed a subscription plan so landing page does not crash
        self.plan = Subscription.objects.create(
            name="GOLD",
            price=999.00,
            duration=30,
            description="Gold Plan"
        )
        self.user = User.objects.create_user(username="existinguser", email="existing@example.com", password="password123")

    def test_landing_page(self):
        response = self.client.get(reverse('page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing_page/page.html')
        self.assertIn('plans', response.context)

    def test_how_it_works(self):
        response = self.client.get(reverse('how_it_works'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/how-it-works.html')

    def test_signup_success(self):
        response = self.client.post(reverse('auth'), {
            'signup': 'signup',
            'name': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword123',
            'confirm': 'newpassword123'
        })
        # Checks if user was created and redirected to verify-otp
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertRedirects(response, reverse('verify_otp', kwargs={'user_id': new_user.id}))
        
        # Verify EmailOTP object was created
        otp_obj = EmailOTP.objects.filter(user=new_user).first()
        self.assertIsNotNone(otp_obj)
        self.assertFalse(otp_obj.is_verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_signup_password_mismatch(self):
        response = self.client.post(reverse('auth'), {
            'signup': 'signup',
            'name': 'newuser2',
            'email': 'new2@example.com',
            'password': 'newpassword123',
            'confirm': 'different'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser2').exists())

    def test_signup_duplicate_username(self):
        response = self.client.post(reverse('auth'), {
            'signup': 'signup',
            'name': 'existinguser',
            'email': 'unique@example.com',
            'password': 'newpassword123',
            'confirm': 'newpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='unique@example.com').exists())

    def test_signup_duplicate_email(self):
        response = self.client.post(reverse('auth'), {
            'signup': 'signup',
            'name': 'uniqueuser',
            'email': 'existing@example.com',
            'password': 'newpassword123',
            'confirm': 'newpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='uniqueuser').exists())

    def test_verify_otp_success(self):
        otp_obj = EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp="123456",
            is_verified=False
        )
        response = self.client.post(reverse('verify_otp', kwargs={'user_id': self.user.id}), {
            'otp': '123456'
        })
        self.assertRedirects(response, reverse('auth'))
        otp_obj.refresh_from_db()
        self.assertTrue(otp_obj.is_verified)

    def test_verify_otp_failure(self):
        otp_obj = EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp="123456",
            is_verified=False
        )
        response = self.client.post(reverse('verify_otp', kwargs={'user_id': self.user.id}), {
            'otp': '999999'
        })
        self.assertEqual(response.status_code, 200)
        otp_obj.refresh_from_db()
        self.assertFalse(otp_obj.is_verified)

    def test_login_without_verified_otp(self):
        EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp="123456",
            is_verified=False
        )
        response = self.client.post(reverse('auth'), {
            'login': 'login',
            'name': 'existinguser',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_with_verified_otp(self):
        EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp="123456",
            is_verified=True
        )
        response = self.client.post(reverse('auth'), {
            'login': 'login',
            'name': 'existinguser',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('profile'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse('auth'), {
            'login': 'login',
            'name': 'existinguser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_forgot_password_success(self):
        # Must have a verified registration first
        EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp="111111",
            is_verified=True
        )
        response = self.client.post(reverse('forgot_password'), {
            'email': 'existing@example.com'
        })
        # Should redirect to reset_password_verify page
        self.assertRedirects(response, reverse('reset_password_verify', kwargs={'user_id': self.user.id}))
        
        # Verify PasswordResetOTP was created
        reset_otp = PasswordResetOTP.objects.filter(user=self.user).first()
        self.assertIsNotNone(reset_otp)
        self.assertFalse(reset_otp.is_used)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Password Reset OTP – Digital Memory Forensics")

    def test_forgot_password_unverified_account(self):
        # Email exists but EmailOTP is not verified
        EmailOTP.objects.create(
            user=self.user,
            email=self.user.email,
            otp="111111",
            is_verified=False
        )
        response = self.client.post(reverse('forgot_password'), {
            'email': 'existing@example.com'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PasswordResetOTP.objects.filter(user=self.user).exists())

    def test_forgot_password_nonexistent_email(self):
        response = self.client.post(reverse('forgot_password'), {
            'email': 'nonexistent@example.com'
        })
        self.assertEqual(response.status_code, 200)

    def test_reset_password_verify_success(self):
        reset_otp = PasswordResetOTP.objects.create(
            user=self.user,
            otp="123456",
            is_used=False
        )
        response = self.client.post(reverse('reset_password_verify', kwargs={'user_id': self.user.id}), {
            'otp': '123456',
            'password': 'newpassword123',
            'confirm': 'newpassword123'
        })
        self.assertRedirects(response, reverse('auth'))
        reset_otp.refresh_from_db()
        self.assertTrue(reset_otp.is_used)
        
        # Verify user can log in with new password
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword123'))

