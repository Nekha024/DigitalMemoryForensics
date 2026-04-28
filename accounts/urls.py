from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import  verify_otp,auth_page

urlpatterns = [
    path("auth/", auth_page, name="auth"),
    path("verify-otp/<int:user_id>/", verify_otp, name="verify_otp"),
    path("logout/", LogoutView.as_view(next_page="auth"), name="logout"),
]