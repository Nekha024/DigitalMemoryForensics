from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Case
from .forms import CaseForm

@login_required
def home(request):
    case_list = Case.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'cases/home.html', {'case_list': case_list})

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

@login_required
def case_detail(request, case_id):
    case = get_object_or_404(Case, id=case_id, created_by=request.user)
    return render(request, 'cases/case_detail.html', {'case': case})






