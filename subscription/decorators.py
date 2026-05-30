from django.shortcuts import redirect, render # For redirecting and rendering templates
from django.contrib import messages # For showing messages to the user
from .models import UserSubscription # For checking user's subscription status
from django.utils import timezone # For checking subscription expiry
from functools import wraps # For creating the decorator, which means we can wrap any view function with this decorator to enforce subscription checks

def subscription_required(view_func):

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs): # This is the actual function that will replace the original view function when decorated. It takes the same arguments as the original view function.

        if not request.user.is_authenticated:
            return redirect('auth')

        # Get latest subscription
        user_subscription = UserSubscription.objects.filter(
            user=request.user
        ).order_by('-ended_at').first()

        # No subscription at all
        if not user_subscription:

            return render(
                request,
                "subscription/not_subscribed.html",
                {
                    "subscription_status": "none"
                }
            )

        # Expired subscription
        if user_subscription.ended_at < timezone.now(): # If subscription has expired, mark it as inactive

            user_subscription.active = False  # Mark subscription as inactive
            user_subscription.save()  # Save the updated subscription status

            return render(
                request,
                "subscription/not_subscribed.html",
                {
                    "subscription_status": "expired"
                }
            )

        # Active subscription
        return view_func(request, *args, **kwargs) # If subscription is active, proceed to the original view function with the original arguments, *args and **kwargs allow us to pass any number of positional and keyword arguments to the original view function without having to explicitly define them in the decorator.

    return _wrapped_view