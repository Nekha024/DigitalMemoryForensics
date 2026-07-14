from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from cases.models import Case
from subscription.models import Subscription, UserSubscription
from django.utils import timezone
from datetime import timedelta

class CasesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="caseuser", email="case@example.com", password="password123")
        self.plan = Subscription.objects.create(name="PREMIUM", price=1999, duration=30, description="Premium Plan")
        
        # Give the user an active subscription so subscription_required passes
        self.user_sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            ended_at=timezone.now() + timedelta(days=30),
            active=True
        )
        
        # Log the user in
        self.client.force_login(self.user)

    def test_profile_view_get(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cases/profile.html')
        self.assertEqual(response.context['total_cases'], 0)
        self.assertEqual(response.context['plans'].plan.name, "PREMIUM")

    def test_profile_view_post_update_success(self):
        response = self.client.post(reverse('profile'), {
            'username': 'newcaseuser',
            'email': 'newcase@example.com'
        })
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newcaseuser')
        self.assertEqual(self.user.email, 'newcase@example.com')

    def test_profile_view_post_empty_fields(self):
        response = self.client.post(reverse('profile'), {
            'username': '',
            'email': ''
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'caseuser')

    def test_dashboard_view(self):
        Case.objects.create(title="Case 1", description="Desc 1", created_by=self.user, status="open")
        Case.objects.create(title="Case 2", description="Desc 2", created_by=self.user, status="closed")
        
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cases/dashboard.html')
        self.assertEqual(response.context['total_cases'], 2)
        self.assertEqual(response.context['open_cases'], 1)
        self.assertEqual(response.context['closed_cases'], 1)

    def test_home_view_lists_cases(self):
        Case.objects.create(title="Test Case A", description="Desc A", created_by=self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cases/home.html')
        self.assertEqual(len(response.context['case_list']), 1)
        self.assertEqual(response.context['case_list'][0].title, "Test Case A")

    def test_create_case_view(self):
        # GET page
        response = self.client.get(reverse('create_case'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cases/create_case.html')

        # POST creation
        response = self.client.post(reverse('create_case'), {
            'title': 'New Forensic Case',
            'description': 'Description of forensic case',
            'status': 'open',
            'case_type': 'memory'
        })
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(Case.objects.filter(title='New Forensic Case', created_by=self.user).exists())

    def test_case_detail_view(self):
        case = Case.objects.create(title="Case B", description="Desc B", created_by=self.user)
        response = self.client.get(reverse('case_detail', kwargs={'case_id': case.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cases/case_detail.html')
        self.assertEqual(response.context['case'].title, "Case B")
