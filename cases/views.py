from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Case
from .forms import CaseForm
from subscription.decorators import subscription_required
from subscription.models import UserSubscription
from django.utils import timezone as tz

@login_required
def profile(request):
    total_cases = Case.objects.filter(created_by=request.user).count()
    plans=UserSubscription.objects.filter(user=request.user,active=True).first()
    remaining_days = None

    if plans:
        remaining_days = max(
            0,
            (plans.ended_at - tz.now()).days
        )
    return render(request, "cases/profile.html", {
        "total_cases": total_cases,'plans':plans,'remaining_days':remaining_days
        })

@login_required
def dashboard(request):

    total_cases = Case.objects.filter(
        created_by=request.user
    ).count()

    open_cases = Case.objects.filter(
        created_by=request.user,
        status='Open'
    ).count()

    closed_cases = Case.objects.filter(
        created_by=request.user,
        status='Closed'
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

    context = {
        "total_cases": total_cases,
        "open_cases": open_cases,
        "closed_cases": closed_cases,
        "recent_cases": recent_cases,
        "remaining_days": remaining_days,
        "months": ["Jan","Feb","Mar","Apr","May","Jun"],
        "monthly_counts": [2,5,3,7,4,6]
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






