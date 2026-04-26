from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .models import EmailOTP
from .utils import generate_otp, send_otp_email


def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            otp_obj = EmailOTP.objects.filter(user=user).first()

            if otp_obj and otp_obj.is_verified:
                login(request, user)
                return redirect("home")
            else:
                messages.error(request, "Please verify your email using OTP before login.")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "accounts/login.html")


def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("register")

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
        messages.success(request, "OTP sent to your email. Check terminal output.")
        return redirect("verify_otp", user_id=user.id)

    return render(request, "accounts/register.html")


def verify_otp(request, user_id):
    user = get_object_or_404(User, id=user_id)
    otp_obj = get_object_or_404(EmailOTP, user=user)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")

        if otp_obj.otp == entered_otp:
            otp_obj.is_verified = True
            otp_obj.save()
            messages.success(request, "Email verified successfully. You can now login.")
            return redirect("custom_login")
        else:
            messages.error(request, "Invalid OTP")

    return render(request, "accounts/verify_otp.html", {"user": user})