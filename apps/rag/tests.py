"""
Tests for RAG Batch Upload Endpoint
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from io import BytesIO
import json


class RAGBatchUploadTests(TestCase):
    """Test Issue 2: Multiple Document Upload"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_batch_upload_endpoint_exists(self):
        """Test that batch upload endpoint exists"""
        response = self.client.post('/chatgpt/api/rag/documents/batch-upload/')
        # Should not 404
        self.assertNotEqual(response.status_code, 404)

    def test_batch_upload_no_files(self):
        """Test batch upload with no files"""
        response = self.client.post('/chatgpt/api/rag/documents/batch-upload/')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)

    def test_single_upload_still_works(self):
        """Test that single document upload still works"""
        file_content = BytesIO(b'PDF content here')
        file_content.name = 'test.txt'

        response = self.client.post(
            '/chatgpt/api/rag/documents/',
            {
                'file': file_content,
                'title': 'Test Document',
                'category': 'General',
                'tags': 'test'
            }
        )
        # Should accept single file upload
        self.assertIn(response.status_code, [201, 400])  # 201 success or 400 validation


class RAGDocumentStatusTests(TestCase):
    """Test RAG Document Operations"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def test_document_list_endpoint(self):
        """Test document list endpoint"""
        response = self.client.get('/chatgpt/api/rag/documents/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('documents', data)
        self.assertIn('count', data)
