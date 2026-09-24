import unittest
from unittest.mock import Mock
from apps.terrameshes.domain.entities import ProcessingTask, TaskStatus
from apps.terrameshes.application.use_cases import RequestProcessingUseCase


class TestRequestProcessingUseCase(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.ai_service = Mock()
        self.storage = Mock()
        self.use_case = RequestProcessingUseCase(self.repo, self.ai_service, self.storage)

    def test_execute_creates_task_and_triggers_ai(self):
        # Arrange
        user_id = 1
        s3_key = "images/scan1.zip"
        self.storage.check_file_exists.return_value = True
        self.ai_service.trigger_processing.return_value = True

        task = self.use_case.execute(user_id, s3_key, "3D")

        self.repo.save.assert_called_once()
        self.assertEqual(task.status, TaskStatus.PROCESSING)
        self.ai_service.trigger_processing.assert_called_once()

    def test_execute_fails_if_s3_file_missing(self):
        self.storage.check_file_exists.return_value = False

        with self.assertRaises(ValueError):
            self.use_case.execute(1, "missing.zip", "3D")
