from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Subscription(models.Model):
    name= models.CharField(max_length=100)
    price=models.DecimalField(max_digits=10,decimal_places=5)
    duration=models.IntegerField()
    description=models.TextField()

class UserSubcription(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    plan=models.ForeignKey(Subscription,on_delete=models.CASCADE)
    create_at=models.DateTimeField(auto_now_add=True)
    ended_at=models.DateTimeField()
    active=models,models.BooleanField(default=True)
