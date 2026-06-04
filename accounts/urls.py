from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import  verify_otp,auth_page,page,how_it_works

urlpatterns = [
    path('',page, name='page'),
    path("auth/", auth_page, name="auth"),
    path("verify-otp/<int:user_id>/", verify_otp, name="verify_otp"),
    path("logout/", LogoutView.as_view(next_page="auth"), name="logout"),
     path("how-it-works/", how_it_works, name="how_it_works"),
]