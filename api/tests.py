from django.test import TestCase

# Create your tests here.

from unittest.mock import patch, Mock
import json
from django.conf import settings


class SendTestTestCase(TestCase):
    @patch("api.views.requests.post")
    @patch("api.views.config")
    def test_send_test(self, mock_config, mock_post):
        # Setup mocks
        mock_config.return_value = "http://test-whatsapp-url"

        mock_response = Mock()
        expected_response = {"status": "success", "message_id": "12345"}
        mock_response.json.return_value = expected_response
        mock_post.return_value = mock_response

        # Call the function (import it inside test to ensure mocks are active if needed,
        # but here we are patching where it is used 'api.views')
        from api.views import send_test

        # Test data
        phone_number = "9876543210"
        text = "Hello World"

        # Execute
        result = send_test(None, phone_number, text)

        # Verify
        self.assertEqual(result, expected_response)

        # Verify config call
        mock_config.assert_called_with("WHATSAPP_URL")

        # Verify requests.post call
        expected_url = "http://test-whatsapp-url/external/send-text"
        expected_json = {"to": "919876543210", "text": text}
        mock_post.assert_called_once_with(expected_url, json=expected_json)

    @patch("api.views.requests.post")
    @patch("api.views.config")
    def test_send_test_already_prefixed(self, mock_config, mock_post):
        # Setup mocks
        mock_config.return_value = "http://test-whatsapp-url"

        mock_response = Mock()
        expected_response = {"status": "success"}
        mock_response.json.return_value = expected_response
        mock_post.return_value = mock_response

        from api.views import send_test

        # Test data with prefix
        phone_number = "919876543210"
        text = "Hello"

        # Execute
        result = send_test(None, phone_number, text)

        # Verify requests.post call uses number as is (formatted)
        expected_url = "http://test-whatsapp-url/external/send-text"
        expected_json = {"to": "919876543210", "text": text}
        mock_post.assert_called_once_with(expected_url, json=expected_json)

    def test_number_format_invalid_non_digit(self):
        from api.views import number_format

        with self.assertRaises(Exception) as cm:
            number_format("12345abcde")
        self.assertEqual(str(cm.exception), "Phone number must contain only digits")

    def test_number_format_invalid_length(self):
        from api.views import number_format

        with self.assertRaises(Exception) as cm:
            number_format("123")
        self.assertEqual(
            str(cm.exception), "Issue With Phone No, Provide a Valid Phone No"
        )
