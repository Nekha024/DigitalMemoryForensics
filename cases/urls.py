from django.urls import path
from . import views

 
urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('', views.home, name='home'),
    path('create/', views.create_case, name='create_case'),
    path('<int:case_id>/', views.case_detail, name='case_detail'),
]