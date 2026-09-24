import unittest
from unittest.mock import Mock
from .use_cases import StartProcessingUseCase
from .interfaces import IJobRepository, IQueueService
from .entities import JobEntity
from .exceptions import BusinessRuleValidationException


class TestStartProcessingUseCase(unittest.TestCase):
    def setUp(self):
        self.mock_repo = Mock(spec=IJobRepository)
        self.mock_queue = Mock(spec=IQueueService)
        self.use_case = StartProcessingUseCase(self.mock_repo, self.mock_queue)

    def test_execute_success(self):
        # Arrange
        self.mock_repo.dataset_exists.return_value = True
        self.mock_repo.create_job.return_value = JobEntity(
            dataset_id=1, resolution_gsd=5.0, radiometric_calibration=True, id=100, job_uid="abc-123"
        )

        # Act
        result = self.use_case.execute(1, 5.0, True)

        # Assert
        self.mock_repo.create_job.assert_called_once()
        self.mock_queue.push_job_to_queue.assert_called_once_with(100)
        self.assertEqual(result.status, "pending")

    def test_validation_error_negative_resolution(self):
        # Act & Assert
        with self.assertRaises(BusinessRuleValidationException):
            self.use_case.execute(1, -2.0, True)

        # Ensure nothing touched DB
        self.mock_repo.create_job.assert_not_called()
