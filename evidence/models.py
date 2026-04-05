from django.db import models
from cases.models import Case

class EvidenceFile(models.Model):
    FILE_TYPES = [
        ('pdf', 'PDF'),
        ('txt', 'Text'),
        ('docx', 'DOCX'),
        ('other', 'Other'),
    ]

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='evidence_files')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='evidence/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other')
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title