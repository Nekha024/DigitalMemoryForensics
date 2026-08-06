from django.urls import path
from .views import subscription_page,payment_success

 
urlpatterns = [
    path('', subscription_page, name='subscription_page'),
    path('payment-success/',payment_success, name='payment_success'),
]