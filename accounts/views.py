from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import EmailOTP, PasswordResetOTP
from .utils import generate_otp, send_otp_email, send_reset_otp_email
from subscription.models import Subscription



#homepage

def page(request):
    plans=Subscription.objects.all()
    return render(request, 'landing_page/page.html',{'plans':plans})

# login
def auth_page(request):
    if request.method == "POST" and 'login' in request.POST:
        username = request.POST.get("name")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            otp_obj = EmailOTP.objects.filter(user=user).first()

            if otp_obj and otp_obj.is_verified:
                login(request, user)
                return redirect("dashboard")
            else:
                messages.error(request, "Please verify your email using OTP before login.", extra_tags='login')
        else:
            messages.error(request, "Invalid username or password", extra_tags='login')

        return render(request, "accounts/auth.html")

# register

    if request.method == "POST" and 'signup' in request.POST:
        username = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request,"accounts/auth.html")

        # Check for existing username
        existing_by_username = User.objects.filter(username=username).first()
        if existing_by_username:
            otp_record = EmailOTP.objects.filter(user=existing_by_username).first()
            if otp_record and not otp_record.is_verified:
                # Stale unverified account — clean it up and allow re-registration
                existing_by_username.delete()
            else:
                messages.error(request, "Username already exists")
                return render(request, "accounts/auth.html")

        # Check for existing email
        existing_by_email = User.objects.filter(email=email).first()
        if existing_by_email:
            otp_record = EmailOTP.objects.filter(user=existing_by_email).first()
            if otp_record and not otp_record.is_verified:
                # Stale unverified account — clean it up and allow re-registration
                existing_by_email.delete()
            else:
                messages.error(request, "Email already exists")
                return render(request, "accounts/auth.html")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        otp = generate_otp()

        EmailOTP.objects.create(
            user=user,
            email=email,
            otp=otp,
            is_verified=False
        )

        send_otp_email(email, otp)
        print(otp)
        messages.success(request, "OTP sent to your email. Check terminal output.")
        return redirect("verify_otp", user_id=user.id)

    return render(request, "accounts/auth.html")


def verify_otp(request, user_id):
    user = get_object_or_404(User, id=user_id)
    otp_obj = get_object_or_404(EmailOTP, user=user)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")

        if otp_obj.otp == entered_otp:
            otp_obj.is_verified = True
            otp_obj.save()
            messages.success(request, "Email verified successfully. You can now login.")
            return redirect("auth")
        else:
            messages.error(request, "Invalid OTP")

    return render(request, "accounts/verify_otp.html", {"user": user})


def forgot_password(request):
    """Step 1: Accept email, send reset OTP."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email address.", extra_tags='forgot')
            return render(request, "accounts/auth.html", {"show_forgot": True})

        # Only allow verified accounts to reset password
        otp_record = EmailOTP.objects.filter(user=user).first()
        if not otp_record or not otp_record.is_verified:
            messages.error(request, "This account hasn't been verified yet. Complete registration first.", extra_tags='forgot')
            return render(request, "accounts/auth.html", {"show_forgot": True})

        # Generate and store reset OTP (overwrite any previous)
        otp = generate_otp()
        PasswordResetOTP.objects.update_or_create(
            user=user,
            defaults={"otp": otp, "is_used": False}
        )
        send_reset_otp_email(email, otp)
        return redirect("reset_password_verify", user_id=user.id)

    return render(request, "accounts/auth.html", {"show_forgot": True})


def reset_password_verify(request, user_id):
    """Step 2: Verify reset OTP and set a new password."""
    user = get_object_or_404(User, id=user_id)
    reset_obj = get_object_or_404(PasswordResetOTP, user=user)

    if reset_obj.is_used:
        messages.error(request, "This reset link has already been used. Please request a new one.", extra_tags='login')
        return redirect("auth")

    if request.method == "POST":
        entered_otp    = request.POST.get("otp", "")
        new_password   = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm", "")

        if reset_obj.otp != entered_otp:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, "accounts/reset_password.html", {"user": user})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/reset_password.html", {"user": user})

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "accounts/reset_password.html", {"user": user})

        user.set_password(new_password)
        user.save()
        reset_obj.is_used = True
        reset_obj.save()
        messages.success(request, "Password reset successfully! Please login with your new password.", extra_tags='login')
        return redirect("auth")

    return render(request, "accounts/reset_password.html", {"user": user})


def how_it_works(request):
    return render(request, "accounts/how-it-works.html")