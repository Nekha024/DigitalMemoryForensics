import razorpay
import uuid
import logging

from datetime import timedelta

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Subscription, UserSubscription

logger = logging.getLogger(__name__)


client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@login_required
def subscription_page(request):

    plans = Subscription.objects.all()

    if request.method == "POST":

        plan_id = request.POST.get('plan_id')

        billing_type = request.POST.get('billing_type')

        plan = Subscription.objects.get(id=plan_id)

        # MONTHLY
        if billing_type == "month":

            final_price = int(plan.price)

            duration = 30

        # 6 MONTHS
        elif billing_type == "six":

            duration = 180

            if plan.name == "SILVER":
                final_price = 799

            elif plan.name == "GOLD":
                final_price = 1099

            else:
                final_price = 1599

        # 1 YEAR
        else:

            duration = 365

            if plan.name == "SILVER":
                final_price = 1499

            elif plan.name == "GOLD":
                final_price = 1999

            else:
                final_price = 2999

        amount = int(final_price * 100)

        receipt = f"receipt_{uuid.uuid4().hex[:16]}"

        try:
            payment = client.order.create({
                'amount': amount,
                'currency': 'INR',
                'payment_capture': 1,
                'receipt': receipt,
                'notes': {
                    'plan': plan.name,
                    'user': request.user.username,
                }
            })
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            messages.error(request, f"Payment gateway error: {e}. Please try again.")
            return redirect('subscription_page')

        context = {
            'plan': plan,
            'payment': payment,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'final_price': final_price,
            'duration': duration,
            'billing_type': billing_type,
            'user_name': request.user.get_full_name() or request.user.username,
            'user_email': request.user.email,
        }

        return render(request, 'subscription/payment.html', context)

    return render(
        request,
        'subscription/subscription.html',
        {'plans': plans}
    )


@login_required
def payment_success(request):

    if request.method == "POST":

        plan_id = request.POST.get('plan_id')

        duration = request.POST.get('duration')

        razorpay_payment_id = request.POST.get('razorpay_payment_id')

        razorpay_order_id = request.POST.get('razorpay_order_id')

        razorpay_signature = request.POST.get('razorpay_signature')

        plan = Subscription.objects.get(id=plan_id)

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        try:
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            logger.error(f"Razorpay signature verification failed: {e} | params: {params_dict}")
            messages.error(request, "Payment verification failed. Please contact support.")
            return redirect('subscription_page')

        UserSubscription.objects.filter(
            user=request.user,
            active=True
        ).update(active=False)

        UserSubscription.objects.create(
            user=request.user,
            plan=plan,
            ended_at=timezone.now() + timedelta(days=int(duration)),
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            active=True
        )

        return render(request, 'subscription/success.html')

    return redirect('subscription_page')