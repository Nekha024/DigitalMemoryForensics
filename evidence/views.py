from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import EvidenceFile
from .forms import EvidenceFileForm
from .utils import detect_file_type, extract_text
from .vector_utils import index_evidence_file, search_similar_chunks
from .llm_utils import generate_rag_answer, DEFAULT_LLM_PROVIDER
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


@login_required
def index_evidence(request, evidence_id):
    evidence = get_object_or_404(
        EvidenceFile,
        id=evidence_id,
        case__created_by=request.user
    )

    if evidence.extracted_text:
        index_evidence_file(evidence)

    return redirect('evidence_detail', evidence_id=evidence.id)


@login_required
def semantic_search(request):
    query = request.GET.get('q', '')
    case_id = request.GET.get('case_id')
    results = []
    cases = Case.objects.filter(created_by=request.user)

    selected_case_id = None
    if case_id and case_id.isdigit():
        selected_case_id = int(case_id)

    if query:
        results = search_similar_chunks(query, case_id=selected_case_id, limit=5)

    return render(request, 'evidence/semantic_search.html', {
        'query': query,
        'results': results,
        'cases': cases,
        'selected_case_id': selected_case_id,
    })


@login_required
def rag_query(request):
    question = request.GET.get('q', '')
    case_id = request.GET.get('case_id')
    provider = request.GET.get('provider', DEFAULT_LLM_PROVIDER)

    cases = Case.objects.filter(created_by=request.user)
    selected_case_id = None
    retrieved_chunks = []
    answer_data = None
    error_message = None

    if case_id and case_id.isdigit():
        selected_case_id = int(case_id)

    if question:
        try:
            retrieved_chunks = search_similar_chunks(
                question,
                case_id=selected_case_id,
                limit=5
            )

            answer_data = generate_rag_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                provider=provider
            )

        except Exception as e:
            error_message = str(e)

    return render(request, 'evidence/rag_query.html', {
        'question': question,
        'provider': provider,
        'cases': cases,
        'selected_case_id': selected_case_id,
        'retrieved_chunks': retrieved_chunks,
        'answer_data': answer_data,
        'error_message': error_message,
    })