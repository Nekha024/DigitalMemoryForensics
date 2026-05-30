import razorpay
import uuid
import logging

from datetime import timedelta

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Subscription, UserSubscription

logger = logging.getLogger(__name__)


client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@login_required
def subscription_page(request):

    plans = Subscription.objects.all()

    if request.method == "POST":

        plan_id  = request.POST.get('plan_id')
        billing_type = request.POST.get('billing_type')
        plan = Subscription.objects.get(id=plan_id)

        # ── Price & duration logic ──────────────────────────────
        if billing_type == "month":
            final_price = int(plan.price)
            duration    = 30

        elif billing_type == "six":
            duration = 180
            if plan.name == "SILVER":
                final_price = 799
            elif plan.name == "GOLD":
                final_price = 1099
            else:
                final_price = 1599

        else:  # year
            duration = 365
            if plan.name == "SILVER":
                final_price = 1499
            elif plan.name == "GOLD":
                final_price = 1999
            else:
                final_price = 2999

        amount  = int(final_price * 100)          # paise
        receipt = f"receipt_{uuid.uuid4().hex[:16]}"

        # ── Create Razorpay order ───────────────────────────────
        try:
            payment = client.order.create({
                'amount':          amount,
                'currency':        'INR',
                'payment_capture': 1,
                'receipt':         receipt,
                'notes': {
                    'plan': plan.name,
                    'user': request.user.username,
                }
            })
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            messages.error(request, f"Payment gateway error: {e}. Please try again.")
            return redirect('subscription_page')

        # ── Store plan info in session so callback can read it ──
        # (Razorpay callback_url only sends payment IDs, not custom fields)
        request.session['rzp_plan_id']  = str(plan_id)
        request.session['rzp_duration'] = str(duration)

        context = {
            'plan':         plan,
            'payment':      payment,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'final_price':  final_price,
            'duration':     duration,
            'billing_type': billing_type,
            'user_name':    request.user.get_full_name() or request.user.username,
            'user_email':   request.user.email,
            # Absolute URL so Razorpay can POST back to us
            'callback_url': request.build_absolute_uri(reverse('payment_success')),
        }

        return render(request, 'subscription/payment.html', context)

    return render(request, 'subscription/subscription.html', {'plans': plans})


# csrf_exempt is REQUIRED — Razorpay's callback POST has no Django CSRF token.
# The Razorpay signature verification below is the security check instead.
@csrf_exempt
@login_required
def payment_success(request):

    if request.method == "POST":

        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id   = request.POST.get('razorpay_order_id')
        razorpay_signature  = request.POST.get('razorpay_signature')

        # Read plan info from session (set in subscription_page)
        plan_id  = request.session.pop('rzp_plan_id',  None)
        duration = request.session.pop('rzp_duration', None)

        if not plan_id or not duration:
            logger.error("Session expired — rzp_plan_id or rzp_duration missing")
            messages.error(request, "Session expired. Please try your payment again.")
            return redirect('subscription_page')

        if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
            logger.error("Missing Razorpay fields in callback POST")
            messages.error(request, "Incomplete payment data received. Please contact support.")
            return redirect('subscription_page')

        # ── Verify signature (proves payment is genuine) ────────
        params_dict = {
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        }

        try:
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            logger.error(f"Razorpay signature verification failed: {e} | params: {params_dict}")
            messages.error(request, "Payment verification failed. Please contact support.")
            return redirect('subscription_page')

        # ── Activate subscription ───────────────────────────────
        plan = Subscription.objects.get(id=plan_id)

        UserSubscription.objects.filter(
            user=request.user, active=True
        ).update(active=False)

        UserSubscription.objects.create(
            user=request.user,
            plan=plan,
            ended_at=timezone.now() + timedelta(days=int(duration)),
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            active=True,
        )

        logger.info(
            f"Subscription activated: user={request.user.username} "
            f"plan={plan.name} duration={duration}d payment={razorpay_payment_id}"
        )

        return render(request, 'subscription/success.html')

    return redirect('subscription_page')