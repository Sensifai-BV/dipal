"""Tests for FMIS webhook tasks."""
import json
import unittest
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase

from accounts.models import Organization, UserModel
from apps.fmis.models import WebhookEndpoint, Job
from apps.fmis.services.sender import WebhookService


class TestWebhookSignature(TestCase):
    """Tests for HMAC signature generation."""

    def test_generate_signature_returns_hex(self):
        """Signature is a valid hex string."""
        sig = WebhookService.generate_signature("my-secret", '{"key": "value"}')
        self.assertIsInstance(sig, str)
        self.assertTrue(len(sig) > 0)
        int(sig, 16)

    def test_empty_secret_returns_empty(self):
        """Empty secret returns empty signature."""
        sig = WebhookService.generate_signature("", '{"key": "value"}')
        self.assertEqual(sig, "")

    def test_same_input_same_output(self):
        """Same secret and payload produce same signature."""
        payload = json.dumps({"event": "test"}, sort_keys=True)
        sig1 = WebhookService.generate_signature("secret", payload)
        sig2 = WebhookService.generate_signature("secret", payload)
        self.assertEqual(sig1, sig2)

    def test_different_secret_different_output(self):
        """Different secrets produce different signatures."""
        payload = json.dumps({"event": "test"}, sort_keys=True)
        sig1 = WebhookService.generate_signature("secret-a", payload)
        sig2 = WebhookService.generate_signature("secret-b", payload)
        self.assertNotEqual(sig1, sig2)


class TestDispatchWebhookEvent(TestCase):
    """Tests for dispatch_webhook_event Celery task."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="fmis@test.com", password="testpass123")
        self.org = Organization.objects.create(name="FMIS Org", user=self.user)
        self.webhook = WebhookEndpoint.objects.create(
            org=self.org,
            url="https://example.com/webhook",
            events=["job.completed", "job.failed"],
            active=True,
        )

    @patch('apps.fmis.tasks.send_single_webhook')
    def test_dispatch_queues_matching_subscribers(self, mock_send):
        """Dispatching queues send_single_webhook for matching subscribers."""
        from apps.fmis.tasks import dispatch_webhook_event

        dispatch_webhook_event("job.completed", {"job_id": "123"})

        mock_send.delay.assert_called_once_with(
            self.webhook.id, "job.completed", {"job_id": "123"}
        )

    @patch('apps.fmis.tasks.send_single_webhook')
    def test_dispatch_skips_unsubscribed_events(self, mock_send):
        """Dispatch does not queue for events the webhook is not subscribed to."""
        from apps.fmis.tasks import dispatch_webhook_event

        dispatch_webhook_event("upload.completed", {"upload_id": "456"})

        mock_send.delay.assert_not_called()

    @patch('apps.fmis.tasks.send_single_webhook')
    def test_dispatch_filters_by_org(self, mock_send):
        """Dispatch with specific_org_id only sends to that org."""
        from apps.fmis.tasks import dispatch_webhook_event

        other_user = UserModel.objects.create_user(email="other@test.com", password="pass123")
        other_org = Organization.objects.create(name="Other Org", user=other_user)
        WebhookEndpoint.objects.create(
            org=other_org,
            url="https://other.com/webhook",
            events=["job.completed"],
            active=True,
        )

        dispatch_webhook_event(
            "job.completed",
            {"job_id": "123"},
            specific_org_id=self.org.id,
        )

        self.assertEqual(mock_send.delay.call_count, 1)
        called_endpoint_id = mock_send.delay.call_args[0][0]
        self.assertEqual(called_endpoint_id, self.webhook.id)

    @patch('apps.fmis.tasks.send_single_webhook')
    def test_dispatch_skips_inactive_webhooks(self, mock_send):
        """Inactive webhooks are not dispatched to."""
        from apps.fmis.tasks import dispatch_webhook_event

        self.webhook.active = False
        self.webhook.save()

        dispatch_webhook_event("job.completed", {"job_id": "123"})

        mock_send.delay.assert_not_called()


class TestSendSingleWebhook(TestCase):
    """Tests for send_single_webhook Celery task."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="sender@test.com", password="testpass123")
        self.org = Organization.objects.create(name="Sender Org", user=self.user)
        self.webhook = WebhookEndpoint.objects.create(
            org=self.org,
            url="https://example.com/hook",
            events=["job.completed"],
            active=True,
        )

    @patch('apps.fmis.tasks.requests.post')
    def test_sends_with_signature(self, mock_post):
        """Webhook is sent with HMAC signature header."""
        from apps.fmis.tasks import send_single_webhook

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        send_single_webhook(self.webhook.id, "job.completed", {"job_id": "abc"})

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get('headers') or call_kwargs[1].get('headers')
        self.assertIn("X-Hub-Signature-256", headers)
        self.assertIn("X-Event-Type", headers)
        self.assertEqual(headers["X-Event-Type"], "job.completed")

    @patch('apps.fmis.tasks.requests.post')
    def test_returns_message_on_success(self, mock_post):
        """Returns status message on successful send."""
        from apps.fmis.tasks import send_single_webhook

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_single_webhook(self.webhook.id, "job.completed", {"job_id": "abc"})
        self.assertIn("Sent", result)

    def test_returns_endpoint_removed_for_missing(self):
        """Returns 'Endpoint Removed' when endpoint no longer exists."""
        from apps.fmis.tasks import send_single_webhook

        fake_id = uuid.uuid4()
        result = send_single_webhook(fake_id, "job.completed", {"job_id": "abc"})
        self.assertEqual(result, "Endpoint Removed")


class TestProcessJobTask(TestCase):
    """Tests for the FMIS process_job_task."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="proc@test.com", password="testpass123")
        self.org = Organization.objects.create(name="Proc Org", user=self.user)
        self.job = Job.objects.create(
            org=self.org,
            input_data={"field": "corn"},
            status="pending",
        )

    @patch('apps.fmis.tasks.dispatch_webhook_event')
    @patch('apps.fmis.tasks.time.sleep')
    def test_successful_processing(self, mock_sleep, mock_dispatch):
        """Successful processing sets status to completed and dispatches webhook."""
        from apps.fmis.tasks import process_job_task

        process_job_task(str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "completed")
        self.assertIsNotNone(self.job.result_data)

        mock_dispatch.delay.assert_called_once()
        call_args = mock_dispatch.delay.call_args
        self.assertEqual(call_args.kwargs['event_type'], 'job.completed')

    @patch('apps.fmis.tasks.dispatch_webhook_event')
    @patch('apps.fmis.tasks.time')
    def test_failed_processing(self, mock_time, mock_dispatch):
        """Failed processing sets status to failed and dispatches failure webhook."""
        from apps.fmis.tasks import process_job_task

        mock_time.sleep.side_effect = RuntimeError("Processing error")

        with self.assertRaises(RuntimeError):
            process_job_task(str(self.job.id))

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "failed")
        self.assertIn("error", self.job.result_data)

        mock_dispatch.delay.assert_called_once()
        call_args = mock_dispatch.delay.call_args
        self.assertEqual(call_args.kwargs['event_type'], 'job.failed')

    def test_missing_job_does_not_crash(self):
        """Task with non-existent job ID does not raise."""
        from apps.fmis.tasks import process_job_task

        fake_id = str(uuid.uuid4())
        process_job_task(fake_id)


if __name__ == "__main__":
    unittest.main()
