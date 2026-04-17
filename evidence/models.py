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
    
class EvidenceChunk(models.Model):
    evidence_file = models.ForeignKey(EvidenceFile, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    qdrant_point_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.evidence_file.title} - Chunk {self.chunk_index}"