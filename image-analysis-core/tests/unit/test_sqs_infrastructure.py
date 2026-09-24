"""Tests for SQS infrastructure: SQSSettings, SQSClient, SQSConsumer."""
import asyncio
import json
import unittest
from unittest.mock import MagicMock, AsyncMock, patch, call

from infrastructure.message_queue.sqs_settings import SQSSettings
from infrastructure.message_queue.sqs_client import SQSClient
from infrastructure.message_queue.sqs_consumer import SQSConsumer


class TestSQSSettings(unittest.TestCase):
    """Test SQS settings configuration."""

    def test_default_values(self):
        """Test that defaults are sensible for local dev (disabled)."""
        settings = SQSSettings(
            _env_file=None,
        )
        self.assertFalse(settings.enabled)
        self.assertEqual(settings.region_name, "eu-north-1")
        self.assertEqual(settings.access_key_id, "")
        self.assertEqual(settings.secret_access_key, "")
        self.assertFalse(settings.use_aws_role)
        self.assertEqual(settings.poll_interval_seconds, 5)
        self.assertEqual(settings.visibility_timeout, 3600)
        self.assertEqual(settings.max_messages_per_poll, 1)
        self.assertEqual(settings.wait_time_seconds, 20)

    @patch.dict("os.environ", {
        "SQS_ENABLED": "true",
        "SQS_REGION_NAME": "us-east-1",
        "SQS_SFM_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/sfm-queue",
        "SQS_CALIBRATION_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/cal-queue",
        "SQS_ORTHOMOSAIC_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/ortho-queue",
        "SQS_USE_AWS_ROLE": "true",
    })
    def test_env_overrides(self):
        """Test that environment variables are picked up."""
        settings = SQSSettings(_env_file=None)
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.region_name, "us-east-1")
        self.assertTrue(settings.use_aws_role)
        self.assertIn("sfm-queue", settings.sfm_queue_url)
        self.assertIn("cal-queue", settings.calibration_queue_url)
        self.assertIn("ortho-queue", settings.orthomosaic_queue_url)

    def test_empty_queue_urls_by_default(self):
        """Test queue URLs are empty by default."""
        settings = SQSSettings(_env_file=None)
        self.assertEqual(settings.calibration_queue_url, "")
        self.assertEqual(settings.sfm_queue_url, "")
        self.assertEqual(settings.orthomosaic_queue_url, "")
        self.assertEqual(settings.calibration_dlq_url, "")
        self.assertEqual(settings.sfm_dlq_url, "")
        self.assertEqual(settings.orthomosaic_dlq_url, "")


class TestSQSClient(unittest.TestCase):
    """Test SQS client wrapper."""

    def setUp(self):
        self.settings = SQSSettings(
            _env_file=None,
            enabled=True,
            region_name="eu-north-1",
            access_key_id="test-key",
            secret_access_key="test-secret",
            calibration_queue_url="https://sqs.eu-north-1.amazonaws.com/123/calibration",
            sfm_queue_url="https://sqs.eu-north-1.amazonaws.com/123/sfm",
            orthomosaic_queue_url="https://sqs.eu-north-1.amazonaws.com/123/orthomosaic",
        )

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_build_client_with_explicit_creds(self, mock_boto3):
        """Test client creation with explicit credentials."""
        client = SQSClient(self.settings)
        mock_boto3.client.assert_called_once()
        call_kwargs = mock_boto3.client.call_args
        self.assertEqual(call_kwargs[0][0], "sqs")
        self.assertEqual(call_kwargs[1]["aws_access_key_id"], "test-key")
        self.assertEqual(call_kwargs[1]["aws_secret_access_key"], "test-secret")

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_build_client_with_iam_role(self, mock_boto3):
        """Test client creation using IAM role (no explicit creds)."""
        self.settings.use_aws_role = True
        client = SQSClient(self.settings)
        mock_boto3.client.assert_called_once()
        call_kwargs = mock_boto3.client.call_args[1]
        self.assertNotIn("aws_access_key_id", call_kwargs)

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_send_message(self, mock_boto3):
        """Test sending a message to SQS."""
        mock_sqs = MagicMock()
        mock_sqs.send_message.return_value = {"MessageId": "msg-123"}
        mock_boto3.client.return_value = mock_sqs

        client = SQSClient(self.settings)
        result = client.send_message(
            self.settings.sfm_queue_url,
            {"job_id": "job-1", "dataset_id": "ds-1"},
        )

        mock_sqs.send_message.assert_called_once_with(
            QueueUrl=self.settings.sfm_queue_url,
            MessageBody=json.dumps({"job_id": "job-1", "dataset_id": "ds-1"}),
        )
        self.assertEqual(result["MessageId"], "msg-123")

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_receive_messages(self, mock_boto3):
        """Test receiving messages from SQS."""
        mock_sqs = MagicMock()
        mock_sqs.receive_message.return_value = {
            "Messages": [
                {"Body": '{"job_id": "job-1"}', "ReceiptHandle": "rh-1"},
            ]
        }
        mock_boto3.client.return_value = mock_sqs

        client = SQSClient(self.settings)
        messages = client.receive_messages(self.settings.sfm_queue_url)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["ReceiptHandle"], "rh-1")

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_receive_messages_empty(self, mock_boto3):
        """Test receiving when queue is empty."""
        mock_sqs = MagicMock()
        mock_sqs.receive_message.return_value = {}
        mock_boto3.client.return_value = mock_sqs

        client = SQSClient(self.settings)
        messages = client.receive_messages(self.settings.sfm_queue_url)
        self.assertEqual(messages, [])

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_delete_message(self, mock_boto3):
        """Test deleting a processed message."""
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs

        client = SQSClient(self.settings)
        client.delete_message(self.settings.sfm_queue_url, "receipt-handle-1")

        mock_sqs.delete_message.assert_called_once_with(
            QueueUrl=self.settings.sfm_queue_url,
            ReceiptHandle="receipt-handle-1",
        )

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_change_visibility(self, mock_boto3):
        """Test extending visibility timeout."""
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs

        client = SQSClient(self.settings)
        client.change_visibility(self.settings.sfm_queue_url, "rh-1", 7200)

        mock_sqs.change_message_visibility.assert_called_once_with(
            QueueUrl=self.settings.sfm_queue_url,
            ReceiptHandle="rh-1",
            VisibilityTimeout=7200,
        )

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_get_queue_url_valid(self, mock_boto3):
        """Test getting queue URL for valid service names."""
        mock_boto3.client.return_value = MagicMock()
        client = SQSClient(self.settings)

        self.assertEqual(
            client.get_queue_url("sfm"),
            self.settings.sfm_queue_url,
        )
        self.assertEqual(
            client.get_queue_url("calibration"),
            self.settings.calibration_queue_url,
        )
        self.assertEqual(
            client.get_queue_url("orthomosaic"),
            self.settings.orthomosaic_queue_url,
        )

    @patch("infrastructure.message_queue.sqs_client.boto3")
    def test_get_queue_url_invalid(self, mock_boto3):
        """Test that unknown service name raises ValueError."""
        mock_boto3.client.return_value = MagicMock()
        client = SQSClient(self.settings)

        with self.assertRaises(ValueError):
            client.get_queue_url("unknown_service")


class TestSQSConsumer(unittest.IsolatedAsyncioTestCase):
    """Test SQS consumer polling and message handling."""

    def _make_client(self, messages=None):
        """Create a mock SQS client with optional prefilled messages."""
        mock_client = MagicMock(spec=SQSClient)
        mock_client.settings = SQSSettings(
            _env_file=None,
            poll_interval_seconds=0,
        )
        if messages is None:
            messages = []
        mock_client.receive_messages.return_value = messages
        mock_client.delete_message.return_value = None
        return mock_client

    async def test_start_and_stop(self):
        """Test consumer can start and stop cleanly."""
        mock_client = self._make_client()
        handler = AsyncMock()

        consumer = SQSConsumer(
            sqs_client=mock_client,
            queue_url="https://sqs.example.com/test-queue",
            handler=handler,
            service_name="test",
        )

        await consumer.start()
        self.assertTrue(consumer._running)
        self.assertIsNotNone(consumer._task)

        await consumer.stop()
        self.assertFalse(consumer._running)

    async def test_double_start_is_noop(self):
        """Test calling start twice is safe."""
        mock_client = self._make_client()
        handler = AsyncMock()

        consumer = SQSConsumer(
            sqs_client=mock_client,
            queue_url="https://sqs.example.com/test-queue",
            handler=handler,
            service_name="test",
        )

        await consumer.start()
        first_task = consumer._task
        await consumer.start()
        self.assertIs(consumer._task, first_task)
        await consumer.stop()

    async def test_processes_message_and_deletes(self):
        """Test that a valid message is processed and deleted."""
        message_body = {"job_id": "job-1", "dataset_id": "ds-1"}
        messages = [
            {
                "Body": json.dumps(message_body),
                "ReceiptHandle": "rh-1",
            }
        ]

        mock_client = self._make_client(messages)
        handler = AsyncMock()

        call_count = 0
        original_receive = mock_client.receive_messages

        def receive_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return messages
            return []

        mock_client.receive_messages.side_effect = receive_once

        consumer = SQSConsumer(
            sqs_client=mock_client,
            queue_url="https://sqs.example.com/test-queue",
            handler=handler,
            service_name="test",
        )

        await consumer.start()
        await asyncio.sleep(0.1)
        await consumer.stop()

        handler.assert_called_once_with(message_body)
        mock_client.delete_message.assert_called_once_with(
            "https://sqs.example.com/test-queue",
            "rh-1",
        )

    async def test_invalid_json_deleted(self):
        """Test that invalid JSON messages are deleted (not retried)."""
        messages = [
            {
                "Body": "NOT-VALID-JSON{{{",
                "ReceiptHandle": "rh-bad",
            }
        ]

        call_count = 0

        def receive_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return messages
            return []

        mock_client = self._make_client()
        mock_client.receive_messages.side_effect = receive_once
        handler = AsyncMock()

        consumer = SQSConsumer(
            sqs_client=mock_client,
            queue_url="https://sqs.example.com/test-queue",
            handler=handler,
            service_name="test",
        )

        await consumer.start()
        await asyncio.sleep(0.1)
        await consumer.stop()

        handler.assert_not_called()
        mock_client.delete_message.assert_called_once_with(
            "https://sqs.example.com/test-queue",
            "rh-bad",
        )

    async def test_handler_failure_does_not_delete_message(self):
        """Test that on handler failure the message stays in queue (for DLQ)."""
        message_body = {"job_id": "fail-job"}
        messages = [
            {
                "Body": json.dumps(message_body),
                "ReceiptHandle": "rh-fail",
            }
        ]

        call_count = 0

        def receive_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return messages
            return []

        mock_client = self._make_client()
        mock_client.receive_messages.side_effect = receive_once

        handler = AsyncMock(side_effect=RuntimeError("processing failed"))

        consumer = SQSConsumer(
            sqs_client=mock_client,
            queue_url="https://sqs.example.com/test-queue",
            handler=handler,
            service_name="test",
        )

        await consumer.start()
        await asyncio.sleep(0.1)
        await consumer.stop()

        handler.assert_called_once_with(message_body)
        mock_client.delete_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
