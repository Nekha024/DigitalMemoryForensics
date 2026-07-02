from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import verify_otp, auth_page, page, how_it_works, forgot_password, reset_password_verify

urlpatterns = [
    path('', page, name='page'),
    path("auth/", auth_page, name="auth"),
    path("verify-otp/<int:user_id>/", verify_otp, name="verify_otp"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/<int:user_id>/", reset_password_verify, name="reset_password_verify"),
    path("logout/", LogoutView.as_view(next_page="auth"), name="logout"),
    path("how-it-works/", how_it_works, name="how_it_works"),
]