from django.db import models
from django.contrib.auth.models import User

class Case(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    TYPE_CHOICES = [
        ('memory', 'Memory Forensics'),
        ('disk', 'Disk Forensics'),
        ('network', 'Network Analysis'),
        ('mobile', 'Mobile Forensics'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cases')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    case_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='memory')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title