from django.urls import path
from . import views

 
urlpatterns = [
    path("profile/", views.profile, name="profile"), 
    path('cases/mycase', views.home, name='home'),
    path('cases/create/', views.create_case, name='create_case'),
    path('cases/<int:case_id>/', views.case_detail, name='case_detail'),
]