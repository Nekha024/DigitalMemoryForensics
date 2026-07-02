import os
import shutil
import tempfile
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock

import chromadb
from cases.models import Case
from evidence.models import EvidenceFile, EvidenceChunk
from evidence.utils import detect_file_type, extract_text
from evidence.vector_utils import chunk_text, get_chroma_client, get_embedding_model
from subscription.models import Subscription, UserSubscription
from django.utils import timezone
from datetime import timedelta

class MockSentenceTransformer:
    def encode(self, sentences, **kwargs):
        import numpy as np
        if isinstance(sentences, str):
            return np.array([0.1] * 384)
        return np.array([[0.1] * 384 for _ in sentences])


class EvidenceUtilsTests(TestCase):
    def test_detect_file_type(self):
        self.assertEqual(detect_file_type("test.pdf"), "pdf")
        self.assertEqual(detect_file_type("TEST.TXT"), "txt")
        self.assertEqual(detect_file_type("document.docx"), "docx")
        self.assertEqual(detect_file_type("image.png"), "other")

    def test_extract_text_txt(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Hello World. This is a digital forensics test.")
            f_path = f.name
        try:
            text = extract_text(f_path, "txt")
            self.assertEqual(text, "Hello World. This is a digital forensics test.")
        finally:
            os.remove(f_path)


class EvidenceVectorTests(TestCase):
    def setUp(self):
        get_chroma_client.cache_clear()
        get_embedding_model.cache_clear()
        # We patch chroma client to use an in-memory ephemeral client for tests
        self.chroma_patcher = patch('evidence.vector_utils.get_chroma_client')
        self.mock_chroma_client = self.chroma_patcher.start()
        self.ephemeral_client = chromadb.EphemeralClient()
        self.mock_chroma_client.return_value = self.ephemeral_client

        # Patch SentenceTransformer to avoid loading 120MB model from network
        self.model_patcher = patch('evidence.vector_utils.get_embedding_model')
        self.mock_get_model = self.model_patcher.start()
        self.mock_get_model.return_value = MockSentenceTransformer()

        self.user = User.objects.create_user(username="vectoruser", password="password123")
        self.case = Case.objects.create(title="Vector Case", created_by=self.user)
        
        # Create a mock file in media root
        self.temp_dir = tempfile.mkdtemp()
        self.file_path = os.path.join(self.temp_dir, "test_evidence.txt")
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("Line 1 text. Line 2 text. Line 3 text.")

        self.evidence = EvidenceFile.objects.create(
            case=self.case,
            title="Evidence A",
            file=SimpleUploadedFile("evidence_a.txt", b"Line 1 text. Line 2 text. Line 3 text."),
            file_type="txt",
            extracted_text="Line 1 text. Line 2 text. Line 3 text."
        )

    def tearDown(self):
        self.chroma_patcher.stop()
        self.model_patcher.stop()
        get_chroma_client.cache_clear()
        get_embedding_model.cache_clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_chunk_text(self):
        text = "This is a short text to chunk."
        chunks = chunk_text(text, chunk_size=10, overlap=2)
        self.assertTrue(len(chunks) > 1)
        self.assertEqual(chunks[0], "This is a")

    def test_index_and_search_evidence_file(self):
        from evidence.vector_utils import index_evidence_file, search_similar_chunks
        
        # Index evidence
        num_chunks = index_evidence_file(self.evidence)
        self.assertTrue(num_chunks > 0)
        self.assertEqual(EvidenceChunk.objects.filter(evidence_file=self.evidence).count(), num_chunks)

        # Search similar chunks
        results = search_similar_chunks("Line 1", case_id=self.case.id, limit=5)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['title'], "Evidence A")
        self.assertEqual(results[0]['evidence_id'], self.evidence.id)


class EvidenceViewsTests(TestCase):
    def setUp(self):
        get_chroma_client.cache_clear()
        get_embedding_model.cache_clear()
        self.client = Client()
        self.user = User.objects.create_user(username="evidenceuser", password="password123")
        self.plan = Subscription.objects.create(name="GOLD", price=999, duration=30, description="Gold Plan")
        self.user_sub = UserSubscription.objects.create(
            user=self.user, plan=self.plan, ended_at=timezone.now() + timedelta(days=30), active=True
        )
        self.case = Case.objects.create(title="Evidence Case", created_by=self.user)
        self.client.force_login(self.user)

        # Patch ChromaDB and SentenceTransformer
        self.chroma_patcher = patch('evidence.vector_utils.get_chroma_client')
        self.mock_chroma_client = self.chroma_patcher.start()
        self.ephemeral_client = chromadb.EphemeralClient()
        self.mock_chroma_client.return_value = self.ephemeral_client

        self.model_patcher = patch('evidence.vector_utils.get_embedding_model')
        self.mock_get_model = self.model_patcher.start()
        self.mock_get_model.return_value = MockSentenceTransformer()

    def tearDown(self):
        self.chroma_patcher.stop()
        self.model_patcher.stop()
        get_chroma_client.cache_clear()
        get_embedding_model.cache_clear()

    def test_upload_evidence_get(self):
        response = self.client.get(reverse('upload_evidence'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'evidence/upload_evidence.html')

    def test_upload_evidence_post_success(self):
        uploaded_file = SimpleUploadedFile("forensic_logs.txt", b"Log entry 1: Alert. Log entry 2: Warning.")
        response = self.client.post(reverse('upload_evidence'), {
            'case': self.case.id,
            'title': 'Forensic Logs',
            'file': uploaded_file
        })
        self.assertRedirects(response, reverse('case_detail', kwargs={'case_id': self.case.id}))
        self.assertTrue(EvidenceFile.objects.filter(title='Forensic Logs', case=self.case).exists())

    def test_evidence_detail_view(self):
        evidence = EvidenceFile.objects.create(
            case=self.case,
            title="E-Logs",
            file=SimpleUploadedFile("elogs.txt", b"log content"),
            file_type="txt",
            extracted_text="log content"
        )
        response = self.client.get(reverse('evidence_detail', kwargs={'evidence_id': evidence.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'evidence/evidence_detail.html')
        self.assertEqual(response.context['evidence'].title, "E-Logs")

    def test_index_evidence_view(self):
        evidence = EvidenceFile.objects.create(
            case=self.case,
            title="E-Logs 2",
            file=SimpleUploadedFile("elogs2.txt", b"log content 2"),
            file_type="txt",
            extracted_text="log content 2"
        )
        response = self.client.get(reverse('index_evidence', kwargs={'evidence_id': evidence.id}))
        self.assertRedirects(response, reverse('evidence_detail', kwargs={'evidence_id': evidence.id}))
        # Verification of chunks
        self.assertTrue(EvidenceChunk.objects.filter(evidence_file=evidence).exists())

    def test_semantic_search_view(self):
        response = self.client.get(reverse('semantic_search') + "?q=alert&case_id=" + str(self.case.id))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'evidence/semantic_search.html')

    def test_rag_query_view(self):
        response = self.client.get(reverse('rag_query') + "?q=who+did+it&case_id=" + str(self.case.id))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'evidence/rag_query.html')

    def test_rag_query_ajax_success(self):
        # Create chunk so it's not empty
        evidence = EvidenceFile.objects.create(
            case=self.case,
            title="Details",
            file=SimpleUploadedFile("details.txt", b"The suspect is John Doe."),
            file_type="txt",
            extracted_text="The suspect is John Doe."
        )
        from evidence.vector_utils import index_evidence_file
        index_evidence_file(evidence)

        # Mock the GLM API response
        with patch('evidence.llm_utils.generate_with_glm') as mock_glm:
            mock_glm.return_value = "Based on the evidence, the suspect is John Doe."
            
            response = self.client.get(reverse('rag_query_ajax') + f"?q=suspect&case_id={self.case.id}&provider=glm")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['provider'], 'glm')
            self.assertIn("John Doe", data['data']['answer'])
            self.assertEqual(len(data['data']['sources']), 1)
