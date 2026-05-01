from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_evidence, name='upload_evidence'),
    path('search/', views.semantic_search, name='semantic_search'),
    path('rag/', views.rag_query, name='rag_query'),
    path('<int:evidence_id>/', views.evidence_detail, name='evidence_detail'),
    path('<int:evidence_id>/index/', views.index_evidence, name='index_evidence'),
]