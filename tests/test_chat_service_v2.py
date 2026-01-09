import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

from app.chat_service import ChatService
from app.settings import settings

class MockDataStore:
    def __init__(self):
        self.website_info = {
            "companyName": {"en": "JWL Test", "zh": "JWL测试"}
        }

class TestChatServiceV2(unittest.TestCase):
    def setUp(self):
        self.store = MockDataStore()
        self.service = ChatService(self.store)

    def test_routing_logic(self):
        # Test broad
        is_tech, is_broad = self.service._determine_routing("do you have backpacks")
        self.assertTrue(is_broad)
        self.assertFalse(is_tech)

        # Test technical
        is_tech, is_broad = self.service._determine_routing("what is the reach compliance")
        self.assertTrue(is_tech)
        self.assertFalse(is_broad)

        # Test neither
        is_tech, is_broad = self.service._determine_routing("hello world")
        self.assertFalse(is_tech)
        self.assertFalse(is_broad)

    def test_model_key_detection(self):
        # Default
        key = self.service._get_model_key()
        self.assertEqual(key, "default")

        # Explicit Override (MODEL_TYPE)
        with patch("app.chat_service.settings") as mock_settings:
            mock_settings.model_type = "deepseek"
            mock_settings.llm_backend = "openai"
            mock_settings.llm_model = "gpt-4" # Even if model is gpt-4
            key = self.service._get_model_key()
            self.assertEqual(key, "deepseek")

        # Mock settings (Auto detection when default)
        with patch("app.chat_service.settings") as mock_settings:
            mock_settings.model_type = "default"
            mock_settings.llm_backend = "litellm"
            mock_settings.litellm_model = "ollama/deepseek-r1"
            key = self.service._get_model_key()
            self.assertEqual(key, "deepseek")

        # Mock settings for Qwen (Auto detection)
        with patch("app.chat_service.settings") as mock_settings:
            mock_settings.model_type = "default"
            mock_settings.llm_backend = "litellm"
            mock_settings.litellm_model = "ollama/qwen2.5-7b"
            key = self.service._get_model_key()
            self.assertEqual(key, "qwen")

    @patch("app.chat_service.build_rag_context")
    @patch("app.chat_service.get_kb_rag")
    def test_prepare_llm_messages(self, mock_get_kb, mock_build_rag):
        # Mock RAG
        mock_build_rag.return_value = {
            "context": "Product Info",
            "mode": "rag",
            "hits_summary": []
        }
        mock_kb = MagicMock()
        mock_kb.retrieve.return_value = [{"text": "KB Info", "metadata": {"kb_id": "1", "lang": "en"}, "score": 0.9}]
        mock_get_kb.return_value = mock_kb

        messages = [{"role": "user", "text": "do you have backpacks"}]
        
        # Run
        llm_msgs = self.service.prepare_llm_messages(messages, "en")
        
        # Verify structure
        self.assertEqual(len(llm_msgs), 2)
        self.assertEqual(llm_msgs[0]["role"], "system")
        self.assertIn("JWL Test", llm_msgs[0]["content"])
        self.assertIn("Product Info", llm_msgs[0]["content"])
        self.assertIn("KB Info", llm_msgs[0]["content"])
        
        # Verify routing effect (broad -> prod_k=3, kb_k=1)
        mock_build_rag.assert_called_with(query="do you have backpacks", locale="en", k=3)
        mock_kb.retrieve.assert_called_with("do you have backpacks", locale="en", k=1)

if __name__ == "__main__":
    unittest.main()
