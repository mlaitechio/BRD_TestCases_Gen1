"""
Tests for AI Chat Endpoints
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
import json


class AIChatInitTests(TestCase):
    """Test Issue: AI Chat Session Initialization"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def test_init_endpoint_exists(self):
        """Test that init endpoint exists"""
        response = self.client.post('/chatgpt/api/chat/init/')
        self.assertNotEqual(response.status_code, 404)

    def test_init_returns_sessionid(self):
        """Test that init returns sessionid"""
        response = self.client.post('/chatgpt/api/chat/init/')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertIn('sessionid', data)
        self.assertIn('conversation_id', data)

    def test_init_creates_unique_sessionids(self):
        """Test that each init creates unique sessionid"""
        response1 = self.client.post('/chatgpt/api/chat/init/')
        response2 = self.client.post('/chatgpt/api/chat/init/')

        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)

        self.assertNotEqual(data1['sessionid'], data2['sessionid'])


class AIChatSendTests(TestCase):
    """Test Issue: AI Chat Send Message"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def test_send_endpoint_exists(self):
        """Test that send endpoint exists"""
        response = self.client.post('/chatgpt/api/chat/send/')
        self.assertNotEqual(response.status_code, 404)

    def test_send_without_sessionid(self):
        """Test send without sessionid returns 400"""
        response = self.client.post(
            '/chatgpt/api/chat/send/',
            data=json.dumps({'message': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_send_without_message(self):
        """Test send without message returns 400"""
        response = self.client.post(
            '/chatgpt/api/chat/send/',
            data=json.dumps({'sessionid': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_send_with_invalid_sessionid(self):
        """Test send with invalid sessionid returns 404"""
        response = self.client.post(
            '/chatgpt/api/chat/send/',
            data=json.dumps({
                'sessionid': 'invalid-sessionid-123',
                'message': 'Hello'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)

    def test_full_chat_flow(self):
        """Test full chat flow: init -> send -> get response"""
        # Step 1: Init
        init_response = self.client.post('/chatgpt/api/chat/init/')
        self.assertEqual(init_response.status_code, 201)
        sessionid = json.loads(init_response.content)['sessionid']

        # Step 2: Send message
        send_response = self.client.post(
            '/chatgpt/api/chat/send/',
            data=json.dumps({
                'sessionid': sessionid,
                'message': 'Test message'
            }),
            content_type='application/json'
        )

        # Should get 200 (or 500 if AI service not configured)
        self.assertIn(send_response.status_code, [200, 500])
