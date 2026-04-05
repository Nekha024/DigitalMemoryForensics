from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_evidence, name='upload_evidence'),
    path('<int:evidence_id>/', views.evidence_detail, name='evidence_detail'),
]
