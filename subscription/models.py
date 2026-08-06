from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Subscription(models.Model):
    name= models.CharField(max_length=100)
    price=models.DecimalField(max_digits=10,decimal_places=2)
    duration=models.IntegerField()
    description=models.TextField()

    def __str__(self):
        return self.name

class UserSubscription(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    plan=models.ForeignKey(Subscription,on_delete=models.CASCADE)
    created_at=models.DateTimeField(auto_now_add=True)
    ended_at=models.DateTimeField()
    active=models.BooleanField(default=True)

    razorpay_order_id = models.CharField(max_length=200, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=200, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"