import random
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def _send_email(to_email, subject, text_body, html_body):
    """Internal helper to send an HTML+plain-text email via Django."""
    from_email = settings.DEFAULT_FROM_EMAIL
    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        print(f"[INFO] Email sent successfully to {to_email}")
    except Exception as e:
        print(f"[ERROR] Could not send email to {to_email}: {e}")
        print(f"[INFO] OTP is still visible in the terminal above as a fallback.")


def send_otp_email(email, otp):
    """Send OTP for new account email verification."""
    print("-------------------------------------------------------------------------------")
    print(f"[OTP] Sending to: {email}  |  OTP: {otp}")
    print("-------------------------------------------------------------------------------")

    subject = "Your OTP Verification Code"
    text_body = (
        f"Hello,\n\n"
        f"Your One-Time Password (OTP) for registration is:\n\n"
        f"  {otp}\n\n"
        f"This OTP is valid for a single use. Do not share it with anyone.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"– Digital Memory Forensics Team"
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:30px;">
        <div style="max-width:480px; margin:auto; background:#fff; border-radius:10px;
                    padding:30px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
          <h2 style="color:#1a1a2e; margin-bottom:6px;">🔐 OTP Verification</h2>
          <p style="color:#555;">Use the code below to verify your email address.</p>
          <div style="text-align:center; margin:28px 0;">
            <span style="font-size:38px; font-weight:bold; letter-spacing:10px;
                         color:#4f46e5; background:#eef2ff; padding:14px 28px;
                         border-radius:8px; display:inline-block;">{otp}</span>
          </div>
          <p style="color:#888; font-size:13px;">This OTP is valid for one-time use only.</p>
          <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
          <p style="color:#aaa; font-size:12px; text-align:center;">
            Digital Memory Forensics &mdash; Secure Evidence Management
          </p>
        </div>
      </body>
    </html>
    """
    _send_email(email, subject, text_body, html_body)


def send_reset_otp_email(email, otp):
    """Send OTP for password reset."""
    print("-------------------------------------------------------------------------------")
    print(f"[RESET OTP] Sending to: {email}  |  OTP: {otp}")
    print("-------------------------------------------------------------------------------")

    subject = "Password Reset OTP – Digital Memory Forensics"
    text_body = (
        f"Hello,\n\n"
        f"Your OTP to reset your password is:\n\n"
        f"  {otp}\n\n"
        f"This OTP is valid for a single use. Do not share it with anyone.\n\n"
        f"If you did not request a password reset, please ignore this email.\n\n"
        f"– Digital Memory Forensics Team"
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:30px;">
        <div style="max-width:480px; margin:auto; background:#fff; border-radius:10px;
                    padding:30px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
          <h2 style="color:#1a1a2e; margin-bottom:6px;">🔑 Password Reset OTP</h2>
          <p style="color:#555;">Use the code below to reset your password.</p>
          <div style="text-align:center; margin:28px 0;">
            <span style="font-size:38px; font-weight:bold; letter-spacing:10px;
                         color:#dc2626; background:#fef2f2; padding:14px 28px;
                         border-radius:8px; display:inline-block;">{otp}</span>
          </div>
          <p style="color:#888; font-size:13px;">
            This OTP is valid for one-time use only. Do not share it with anyone.
          </p>
          <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
          <p style="color:#aaa; font-size:12px; text-align:center;">
            Digital Memory Forensics &mdash; Secure Evidence Management
          </p>
        </div>
      </body>
    </html>
    """
    _send_email(email, subject, text_body, html_body)