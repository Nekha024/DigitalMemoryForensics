import razorpay
import uuid
import logging

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core import signing
from django.shortcuts import render, redirect
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

        plan_id      = request.POST.get('plan_id')
        billing_type = request.POST.get('billing_type')
        plan         = Subscription.objects.get(id=plan_id)

        # ── Price & duration ────────────────────────────────────
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

        amount  = int(final_price * 100)
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

        # ── Sign the payload and embed in callback_url ──────────
        # Session cookies are blocked by Chrome SameSite=Lax on cross-site POST,
        # so we encode user/plan/duration into a signed token in the URL itself.
        # Django's signing uses SECRET_KEY — tamper-proof and expires in 1 hour.
        token = signing.dumps(
            {
                'user_id':  request.user.id,
                'plan_id':  int(plan_id),
                'duration': duration,
            },
            salt='rzp_callback',
        )

        callback_url = request.build_absolute_uri(
            reverse('payment_success') + f'?token={token}'
        )

        context = {
            'plan':         plan,
            'payment':      payment,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'final_price':  final_price,
            'duration':     duration,
            'billing_type': billing_type,
            'user_name':    request.user.get_full_name() or request.user.username,
            'user_email':   request.user.email,
            'callback_url': callback_url,
        }

        return render(request, 'subscription/payment.html', context)

    return render(request, 'subscription/subscription.html', {'plans': plans})


# ── payment_success ─────────────────────────────────────────────
# @csrf_exempt  : Razorpay posts here without a Django CSRF token.
# No @login_required : session cookie is blocked by SameSite on the
#                      cross-site POST. Identity is proven by the signed token.
# Security       : Razorpay signature + signed token = double verification.
@csrf_exempt
def payment_success(request):

    if request.method == "POST":

        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id   = request.POST.get('razorpay_order_id')
        razorpay_signature  = request.POST.get('razorpay_signature')

        # ── Decode signed token from URL ────────────────────────
        token = request.GET.get('token')

        if not token:
            logger.error("payment_success called with no token in URL")
            messages.error(request, "Invalid payment link. Please try again.")
            return redirect('subscription_page')

        try:
            # max_age=3600 → token expires after 1 hour
            data     = signing.loads(token, salt='rzp_callback', max_age=3600)
            user_id  = data['user_id']
            plan_id  = data['plan_id']
            duration = data['duration']
        except signing.SignatureExpired:
            logger.error("Razorpay callback token expired")
            messages.error(request, "Payment session expired. Please try again.")
            return redirect('subscription_page')
        except signing.BadSignature:
            logger.error("Razorpay callback token tampered/invalid")
            messages.error(request, "Invalid payment token. Please contact support.")
            return redirect('subscription_page')

        # ── Validate Razorpay fields ────────────────────────────
        if not razorpay_payment_id or not razorpay_order_id or not razorpay_signature:
            logger.error("Missing Razorpay fields in callback POST")
            messages.error(request, "Incomplete payment data. Please contact support.")
            return redirect('subscription_page')

        # ── Verify Razorpay signature ───────────────────────────
        params_dict = {
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        }

        try:
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            logger.error(f"Signature verification failed: {e} | {params_dict}")
            messages.error(request, "Payment verification failed. Contact support.")
            return redirect('subscription_page')

        # ── Activate subscription ───────────────────────────────
        try:
            user = User.objects.get(id=user_id)
            plan = Subscription.objects.get(id=plan_id)
        except (User.DoesNotExist, Subscription.DoesNotExist) as e:
            logger.error(f"User or Plan not found: {e}")
            messages.error(request, "Account error. Please contact support.")
            return redirect('subscription_page')

        UserSubscription.objects.filter(user=user, active=True).update(active=False)

        UserSubscription.objects.create(
            user=user,
            plan=plan,
            ended_at=timezone.now() + timedelta(days=int(duration)),
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            active=True,
        )

        logger.info(
            f"✅ Subscription activated: user={user.username} "
            f"plan={plan.name} duration={duration}d "
            f"payment_id={razorpay_payment_id}"
        )

        return render(request, 'subscription/success.html')

    return redirect('subscription_page')