from django.urls import path,reverse_lazy
from . import views
from django.contrib.auth import views as auth_views
from .forms import CustomPasswordChangeForm

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path("dashboard/",views.dashboard, name="dashboard"),
    path('', views.home, name='home'),
    path('create/', views.create_case, name='create_case'),
    path('<int:case_id>/', views.case_detail, name='case_detail'),

    # Change Password
    path(
        'change_password/',
        auth_views.PasswordChangeView.as_view(
            form_class=CustomPasswordChangeForm,
            template_name='accounts/change_password.html',
            success_url=reverse_lazy('password_changed')
        ),
        name='change_password'
    ),

    # Password Changed Success Page
    path(
        'password_changed/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='accounts/password_changed.html'
        ),
        name='password_changed'
    ),
]