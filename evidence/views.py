from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import EvidenceFile
from .forms import EvidenceFileForm
from .utils import detect_file_type, extract_text
from cases.models import Case
@login_required
def upload_evidence(request):
    if request.method == 'POST':
        form = EvidenceFileForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            evidence = form.save(commit=False)

            if evidence.case.created_by != request.user:
                return redirect('home')

            evidence.file_type = detect_file_type(evidence.file.name)
            evidence.save()

            file_path = evidence.file.path
            evidence.extracted_text = extract_text(file_path, evidence.file_type)
            evidence.save()

            return redirect('case_detail', case_id=evidence.case.id)
    else:
        form = EvidenceFileForm(user=request.user)

    return render(request, 'evidence/upload_evidence.html', {'form': form})

@login_required
def evidence_detail(request, evidence_id):
    evidence = get_object_or_404(
        EvidenceFile,
        id=evidence_id,
        case__created_by=request.user
    )
    return render(request, 'evidence/evidence_detail.html', {'evidence': evidence})