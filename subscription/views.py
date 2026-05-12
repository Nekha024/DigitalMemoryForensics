import razorpay

from datetime import timedelta

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Subscription, UserSubscription


client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

@login_required
def subscription_page(request):

    plans = Subscription.objects.all()

    if request.method == "POST":

        plan_id = request.POST.get('plan_id')

        plan = Subscription.objects.get(id=plan_id)

        amount = int(plan.price * 100)#convert to paisa for rasorpay

        payment = client.order.create({
            'amount': amount,
            'currency': 'INR',
            'payment_capture': '1'
        })

        context = {
            'plan': plan,
            'payment': payment,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
        }

        return render(request, 'subscription/payment.html', context)

    return render(request, 'subscription/subscription.html', {'plans': plans})

@login_required
def payment_success(request):

    if request.method == "POST":

        plan_id = request.POST.get('plan_id')
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')

        plan = Subscription.objects.get(id=plan_id)

        UserSubscription.objects.filter(
            user=request.user,
            active=True
        ).update(active=False)

        UserSubscription.objects.create(
            user=request.user,
            plan=plan,
            ended_at=timezone.now() + timedelta(days=plan.duration),
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            active=True
        )

        return render(request, 'subscription/success.html')

    return redirect('subscription_page')