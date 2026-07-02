from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import signing
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from subscription.models import Subscription, UserSubscription

class SubscriptionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="subuser", email="sub@example.com", password="password123")
        self.plan = Subscription.objects.create(
            name="SILVER",
            price=499.00,
            duration=30,
            description="Silver Plan Description"
        )
        self.client.force_login(self.user)

    def test_subscription_page_lists_plans(self):
        response = self.client.get(reverse('subscription_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'subscription/subscription.html')
        self.assertIn(self.plan, response.context['plans'])

    @patch('subscription.views.client')
    def test_subscription_page_post_initiate(self, mock_razorpay):
        # Mock the order creation
        mock_razorpay.order.create.return_value = {
            'id': 'order_test_123',
            'amount': 49900,
            'currency': 'INR'
        }
        
        response = self.client.post(reverse('subscription_page'), {
            'plan_id': self.plan.id,
            'billing_type': 'month'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'subscription/payment.html')
        self.assertEqual(response.context['plan'], self.plan)
        self.assertEqual(response.context['final_price'], 499)
        self.assertEqual(response.context['duration'], 30)
        
        # Verify order was created with correct fields
        mock_razorpay.order.create.assert_called_once()

    @patch('subscription.views.client')
    def test_payment_success_processing(self, mock_razorpay):
        # Setup signed token
        token = signing.dumps(
            {
                'user_id': self.user.id,
                'plan_id': self.plan.id,
                'duration': 30,
            },
            salt='rzp_callback',
        )
        
        # Mock payment verification (should not raise error)
        mock_razorpay.utility.verify_payment_signature.return_value = True

        response = self.client.post(
            reverse('payment_success') + f'?token={token}',
            {
                'razorpay_payment_id': 'pay_123',
                'razorpay_order_id': 'order_123',
                'razorpay_signature': 'sig_123'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'subscription/success.html')

        # Check that subscription is created and active
        user_sub = UserSubscription.objects.get(user=self.user, active=True)
        self.assertEqual(user_sub.plan, self.plan)
        self.assertEqual(user_sub.razorpay_payment_id, 'pay_123')
        self.assertEqual(user_sub.razorpay_order_id, 'order_123')
        self.assertEqual(user_sub.razorpay_signature, 'sig_123')

    def test_subscription_required_no_subscription(self):
        # Target a view decorated with subscription_required, like cases home page
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'subscription/not_subscribed.html')
        self.assertEqual(response.context['subscription_status'], 'none')

    def test_subscription_required_expired_subscription(self):
        # Create expired subscription
        UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            ended_at=timezone.now() - timedelta(days=1),
            active=True
        )
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'subscription/not_subscribed.html')
        self.assertEqual(response.context['subscription_status'], 'expired')
        
        # Check active status is updated to False
        user_sub = UserSubscription.objects.get(user=self.user)
        self.assertFalse(user_sub.active)

    def test_subscription_required_valid_subscription(self):
        # Create active subscription
        UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            ended_at=timezone.now() + timedelta(days=30),
            active=True
        )
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cases/home.html')
