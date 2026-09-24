"""Unit tests for analysis_mode in the job processing domain."""
import unittest
from unittest.mock import MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestJobEntityAnalysisMode(unittest.TestCase):
    """Test JobEntity with analysis_mode field."""

    def test_default_analysis_mode(self):
        """Default analysis_mode should be 'fast'."""
        from apps.jobs.domains.entities import JobEntity

        entity = JobEntity(
            dataset_id=1,
            resolution_gsd=5.0,
            radiometric_calibration=True,
        )
        self.assertEqual(entity.analysis_mode, "fast")

    def test_explicit_full_mode(self):
        """Explicit full analysis mode."""
        from apps.jobs.domains.entities import JobEntity

        entity = JobEntity(
            dataset_id=1,
            resolution_gsd=5.0,
            radiometric_calibration=True,
            analysis_mode="full",
        )
        self.assertEqual(entity.analysis_mode, "full")


class TestStartProcessingUseCaseAnalysisMode(unittest.TestCase):
    """Test StartProcessingUseCase with analysis_mode parameter."""

    def test_execute_passes_analysis_mode(self):
        """UseCase should pass analysis_mode to JobEntity."""
        from apps.jobs.domains.use_cases import StartProcessingUseCase

        mock_repo = MagicMock()
        mock_repo.dataset_exists.return_value = True
        mock_repo.create_job.side_effect = lambda job: job
        mock_queue = MagicMock()

        use_case = StartProcessingUseCase(
            job_repo=mock_repo, queue_service=mock_queue
        )
        result = use_case.execute(
            dataset_id=1,
            resolution=5.0,
            calibration=True,
            analysis_mode="full",
        )
        self.assertEqual(result.analysis_mode, "full")

    def test_invalid_analysis_mode_raises(self):
        """Invalid analysis_mode should raise validation error."""
        from apps.jobs.domains.use_cases import StartProcessingUseCase
        from apps.jobs.domains.exceptions import BusinessRuleValidationException

        mock_repo = MagicMock()
        mock_repo.dataset_exists.return_value = True
        mock_queue = MagicMock()

        use_case = StartProcessingUseCase(
            job_repo=mock_repo, queue_service=mock_queue
        )
        with self.assertRaises(BusinessRuleValidationException):
            use_case.execute(
                dataset_id=1,
                resolution=5.0,
                calibration=True,
                analysis_mode="invalid",
            )

    def test_default_analysis_mode(self):
        """Default analysis_mode should be 'fast' when not specified."""
        from apps.jobs.domains.use_cases import StartProcessingUseCase

        mock_repo = MagicMock()
        mock_repo.dataset_exists.return_value = True
        mock_repo.create_job.side_effect = lambda job: job
        mock_queue = MagicMock()

        use_case = StartProcessingUseCase(
            job_repo=mock_repo, queue_service=mock_queue
        )
        result = use_case.execute(
            dataset_id=1,
            resolution=5.0,
            calibration=True,
        )
        self.assertEqual(result.analysis_mode, "fast")


if __name__ == "__main__":
    unittest.main()
