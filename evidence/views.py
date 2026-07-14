from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import EvidenceFile
from .forms import EvidenceFileForm
from .utils import detect_file_type, extract_text
from .vector_utils import index_evidence_file, search_similar_chunks
from .llm_utils import generate_rag_answer, DEFAULT_LLM_PROVIDER
from cases.models import Case
from subscription.decorators import subscription_required
from subscription.models import UserSubscription



@subscription_required
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


@subscription_required
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

@subscription_required
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

@subscription_required
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
    user_subscription=UserSubscription.objects.filter(
        user=request.user,
        active=True
        ).first()
    if case_id and case_id.isdigit():
        selected_case_id = int(case_id)

    return render(request, 'evidence/rag_query.html', {
        'question': question,
        'provider': provider,
        'cases': cases,
        'selected_case_id': selected_case_id,
        'retrieved_chunks': retrieved_chunks,
        'answer_data': answer_data,
        'error_message': error_message,
        'user_subscription':user_subscription
    })


@require_GET
def rag_query_ajax(request):
    """Async JSON endpoint called by the frontend via fetch().
    Returns JSON always — never redirects — so the browser fetch() never
    receives an HTML login page and chokes on the DOCTYPE.
    """
    # Manual auth check: return JSON 401 instead of HTML redirect
    if not request.user.is_authenticated:
        return JsonResponse(
            {'ok': False, 'error': 'Session expired. Please refresh the page and log in again.'},
            status=401
        )

    question = request.GET.get('q', '').strip()
    case_id  = request.GET.get('case_id', '')
    provider = request.GET.get('provider', DEFAULT_LLM_PROVIDER).lower()

    if not question:
        return JsonResponse({'ok': False, 'error': 'No question provided.'}, status=400)

    selected_case_id = None
    if case_id and case_id.isdigit():
        selected_case_id = int(case_id)

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
        return JsonResponse({'ok': True, 'data': answer_data, 'provider': provider})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)




from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from subscription.decorators import subscription_required
from .models import EvidenceFile
from .vector_utils import get_collection
import os

@login_required
@subscription_required
@require_POST
def delete_evidence(request, evidence_id):
    # Retrieve evidence and ensure access permission
    evidence = get_object_or_404(EvidenceFile, id=evidence_id, case__created_by=request.user)
    case_id = evidence.case.id
    evidence_title = evidence.title

    # 1. CLEAN CHROMADB VECTOR EMBEDDINGS
    try:
        collection = get_collection()
        # Delete vectors where evidence_id matches
        collection.delete(where={"evidence_id": int(evidence_id)})
    except Exception:
        pass

    # 2. DELETE PHYSICAL FILE FROM DISK
    if evidence.file and os.path.exists(evidence.file.path):
        os.remove(evidence.file.path)

    # 3. DELETE FROM DB
    evidence.delete()

    messages.success(request, f"Evidence '{evidence_title}' deleted successfully.")
    return redirect('case_detail', case_id=case_id)