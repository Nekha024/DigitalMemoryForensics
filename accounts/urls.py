from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import custom_login, register, verify_otp

urlpatterns = [
    path("login/", custom_login, name="custom_login"),
    path("register/", register, name="register"),
    path("verify-otp/<int:user_id>/", verify_otp, name="verify_otp"),
    path("logout/", LogoutView.as_view(next_page="custom_login"), name="logout"),
]