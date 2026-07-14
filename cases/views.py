from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Case
from .forms import CaseForm
from subscription.decorators import subscription_required
from subscription.models import UserSubscription
from django.utils import timezone as tz
from django.contrib import messages
from evidence.models import EvidenceFile

# delete
from django.views.decorators.http import require_POST
import shutil
import os
from evidence.vector_utils import get_collection

@login_required
def profile(request):
    user = request.user

    # Handle Form Submission (POST)
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()

        # Basic server-side validation
        if not username or not email:
            messages.error(request, "Both username and email fields are required.")
        else:
            # Check for unique constraints if username/email changed
            if username != user.username and user.__class__.objects.filter(username=username).exists():
                messages.error(request, "This username is already taken.")
            elif email != user.email and user.__class__.objects.filter(email=email).exists():
                messages.error(request, "This email address is already in use.")
            else:
                # Update user data
                user.username = username
                user.email = email
                user.save()
                messages.success(request, "Your profile parameters have been updated successfully.", extra_tags='profile')
                return redirect("profile")  

    # Handle Page Load (GET)
    plans = UserSubscription.objects.filter(user=user, active=True).first()
    remaining_days = None

    if plans:
        remaining_days = max(
            0,
            (plans.ended_at - tz.now()).days
        )

    return render(request, "cases/profile.html", {
        "plans": plans,
        "remaining_days": remaining_days,
        "password_changed_date": "Not trackable directly via standard user model",


    })
@subscription_required
@login_required
def dashboard(request):

    total_cases = Case.objects.filter(
        created_by=request.user
    ).count()

    open_cases = Case.objects.filter(
        created_by=request.user,
        status='open'
    ).count()

    evidence_count = EvidenceFile.objects.filter(
        case__created_by=request.user
    ).count()

    closed_cases = Case.objects.filter(
        created_by=request.user,
        status='closed'
    ).count()

    recent_cases = Case.objects.filter(
        created_by=request.user
    ).order_by('-created_at')[:5]

    plan = UserSubscription.objects.filter(
        user=request.user,
        active=True
    ).first()

    remaining_days = 0

    if plan:
        remaining_days = (
            plan.ended_at.date() -
            tz.now().date()
        ).days
        
    import datetime
    today = tz.now().date()
    months_data = []
    for i in range(5, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        months_data.append((year, month))

    months = []
    monthly_counts = []
    for y, m in months_data:
        month_name = datetime.date(y, m, 1).strftime("%b")
        count = Case.objects.filter(
            created_by=request.user,
            created_at__year=y,
            created_at__month=m
        ).count()
        months.append(month_name)
        monthly_counts.append(count)

    context = {
        "total_cases": total_cases,
        "open_cases": open_cases,
        "evidence_count": evidence_count,
        "closed_cases": closed_cases,
        "recent_cases": recent_cases,
        "remaining_days": remaining_days,
        "months": months,
        "monthly_counts": monthly_counts
    }

    return render(
        request,
        "cases/dashboard.html",
        context
    )

@subscription_required
@login_required
def home(request):
    case_list = Case.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'cases/home.html', {'case_list': case_list})

@subscription_required
@login_required
def create_case(request):
    if request.method == 'POST':
        
        form = CaseForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.created_by = request.user
            case.save()
            return redirect('home')
    else:
        form = CaseForm()
    return render(request, 'cases/create_case.html', {'form': form})

@subscription_required
@login_required
def case_detail(request, case_id):
    case = get_object_or_404(Case, id=case_id, created_by=request.user)
    return render(request, 'cases/case_detail.html', {'case': case})




@login_required
@subscription_required
@require_POST
def delete_case(request, case_id):
    # Ensure the case belongs to the logged-in user
    case = get_object_or_404(Case, id=case_id, created_by=request.user)
    
    # 1. CLEAN UP CHROMADB VECTORS
    try:
        collection = get_collection()
        # Delete all indexed evidence chunks associated with this case ID
        collection.delete(where={"case_id": int(case_id)})
    except Exception as e:
        # Log error but proceed so DB doesn't get out-of-sync
        pass
    # 2. CLEAN UP PHYSICAL FILES ON DISK
    # Delete the case's media directory (e.g., media/cases/<case_id>/)
    case_media_path = os.path.join('media', 'cases', str(case_id))
    if os.path.exists(case_media_path):
        shutil.rmtree(case_media_path)
    # 3. DELETE FROM RELATIONAL DATABASE
    # If ForeignKey relations are set to on_delete=models.CASCADE, 
    # this will automatically delete EvidenceFiles, EvidenceChunks, etc.
    case.delete()
    messages.success(request, f"Case '{case.title}' and all associated files/vectors were successfully deleted.")
    return redirect('home')



@require_POST
@login_required
def toggle_case_status(request, case_id):
    case = get_object_or_404(Case, id=case_id, created_by=request.user)
    if case.status == 'open':
        case.status = 'closed'
        messages.success(request, f"Case '{case.title}' has been closed.")
    else:
        case.status = 'open'
        messages.success(request, f"Case '{case.title}' has been reopened.")
    case.save()
    return redirect('case_detail', case_id=case.id)


