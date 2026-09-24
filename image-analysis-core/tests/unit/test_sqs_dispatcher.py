"""Tests for SQS dispatcher and dispatch settings."""
import json
import unittest
from unittest.mock import MagicMock, patch

from api_gateway.app.clients.sqs_dispatcher import DispatchSettings, SQSDispatcher
from infrastructure.message_queue.sqs_client import SQSClient
from infrastructure.message_queue.sqs_settings import SQSSettings


class TestDispatchSettings(unittest.TestCase):
    """Test dispatch mode settings."""

    def test_default_mode_is_http(self):
        """Test that default dispatch mode is HTTP for local dev."""
        settings = DispatchSettings(_env_file=None)
        self.assertEqual(settings.mode, "http")

    @patch.dict("os.environ", {"DISPATCH_MODE": "sqs"})
    def test_sqs_mode_from_env(self):
        """Test SQS mode is picked up from environment."""
        settings = DispatchSettings(_env_file=None)
        self.assertEqual(settings.mode, "sqs")


class TestSQSDispatcher(unittest.IsolatedAsyncioTestCase):
    """Test SQS dispatcher job publishing."""

    def setUp(self):
        self.settings = SQSSettings(
            _env_file=None,
            enabled=True,
            calibration_queue_url="https://sqs.example.com/calibration",
            sfm_queue_url="https://sqs.example.com/sfm",
            orthomosaic_queue_url="https://sqs.example.com/orthomosaic",
        )
        self.mock_client = MagicMock(spec=SQSClient)
        self.mock_client.settings = self.settings
        self.mock_client.get_queue_url.side_effect = lambda name: {
            "calibration": self.settings.calibration_queue_url,
            "sfm": self.settings.sfm_queue_url,
            "orthomosaic": self.settings.orthomosaic_queue_url,
        }[name]
        self.mock_client.send_message.return_value = {"MessageId": "msg-1"}
        self.dispatcher = SQSDispatcher(self.mock_client)

    async def test_dispatch_calibration(self):
        """Test dispatching calibration job to SQS."""
        result = await self.dispatcher.dispatch_calibration(
            job_id="job-1_calibration",
            dataset_id="ds-1",
            download_url="s3://bucket/path",
            parameters={"key": "val"},
        )

        self.mock_client.get_queue_url.assert_called_with("calibration")
        self.mock_client.send_message.assert_called_once_with(
            self.settings.calibration_queue_url,
            {
                "job_id": "job-1_calibration",
                "dataset_id": "ds-1",
                "download_url": "s3://bucket/path",
                "parameters": {"key": "val"},
            },
        )
        self.assertEqual(result["MessageId"], "msg-1")

    async def test_dispatch_sfm(self):
        """Test dispatching SFM job to SQS."""
        result = await self.dispatcher.dispatch_sfm(
            job_id="job-1_sfm",
            dataset_id="ds-1",
            download_url=[{"url": "https://example.com/img.jpg", "filename": "img.jpg"}],
            parameters={"resolution_gsd": 5.0},
        )

        self.mock_client.get_queue_url.assert_called_with("sfm")
        sent_msg = self.mock_client.send_message.call_args[0][1]
        self.assertEqual(sent_msg["job_id"], "job-1_sfm")
        self.assertIsInstance(sent_msg["download_url"], list)

    async def test_dispatch_orthomosaic(self):
        """Test dispatching orthomosaic job to SQS."""
        result = await self.dispatcher.dispatch_orthomosaic(
            job_id="job-1_orthomosaic",
            dataset_id="ds-1",
            dataset_path="/app/data/temp/jobs/sfm/job-1_sfm/run_1",
            parameters={"is_multispectral": False},
        )

        self.mock_client.get_queue_url.assert_called_with("orthomosaic")
        sent_msg = self.mock_client.send_message.call_args[0][1]
        self.assertEqual(sent_msg["job_id"], "job-1_orthomosaic")
        self.assertEqual(sent_msg["dataset_path"], "/app/data/temp/jobs/sfm/job-1_sfm/run_1")

    async def test_dispatch_with_default_parameters(self):
        """Test that None parameters become empty dict."""
        await self.dispatcher.dispatch_sfm(
            job_id="job-2_sfm",
            dataset_id="ds-2",
            download_url="s3://bucket/path",
            parameters=None,
        )

        sent_msg = self.mock_client.send_message.call_args[0][1]
        self.assertEqual(sent_msg["parameters"], {})


if __name__ == "__main__":
    unittest.main()
