"""
Load and performance tests for the PhotoGear backend.

Tests system behaviour under concurrent load and measures response times:
- Concurrent user registration and authentication
- Concurrent dataset CRUD operations
- Concurrent job operations with mixed read/write
- Database query performance under bulk data
- Cross-organization isolation under concurrent access
- API throughput and response time thresholds
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Organization, UserModel, Role, RoleName
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus, ProcessingStage
from products.models import Product

RESPONSE_TIME_THRESHOLD_MS = 500
BULK_RESPONSE_TIME_THRESHOLD_MS = 2000
TEST_PASSWORD = "StrongPass123!"


def _timed_request(client, method, url, **kwargs):
    """
    Execute a DRF APIClient request and return (response, elapsed_ms).

    Args:
        client: DRF APIClient instance
        method: HTTP method name (get, post, put, delete)
        url: Request URL path
        **kwargs: Additional arguments forwarded to the client method

    Returns:
        Tuple of (response, elapsed_milliseconds)
    """
    start = time.monotonic()
    response = getattr(client, method)(url, **kwargs)
    elapsed_ms = (time.monotonic() - start) * 1000
    return response, elapsed_ms


def _close_db_connection():
    """Close the thread-local database connection to prevent leaked sessions."""
    connection.close()


def _thread_safe(func):
    """
    Wrap a function to close its DB connection after execution.

    Args:
        func: Callable to wrap

    Returns:
        Wrapped callable that closes DB connection on completion
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            _close_db_connection()
    return wrapper


class LoadTestBase(TransactionTestCase):
    """
    Base class for load tests.

    Uses TransactionTestCase so that threads can see committed data.
    Creates shared roles, users and organizations used across load tests.
    """

    CONCURRENT_USERS = 10

    def setUp(self):
        Role.objects.get_or_create(
            id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"}
        )
        Role.objects.get_or_create(
            id=2, defaults={"name": RoleName.USER, "label": "Owner"}
        )
        self.users = []
        self.clients = []
        for i in range(self.CONCURRENT_USERS):
            user = UserModel.objects.create_user(
                email=f"loaduser{i}@test.com", password=TEST_PASSWORD
            )
            org = Organization.objects.create(name=f"LoadOrg{i}", user=user)
            user.organization = org
            user.save()

            client = APIClient()
            client.force_authenticate(user=user)
            self.users.append(user)
            self.clients.append(client)


class TestConcurrentRegistration(TransactionTestCase):
    """Tests concurrent user registration under load."""

    CONCURRENT_REGISTRATIONS = 15

    def setUp(self):
        Role.objects.get_or_create(
            id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"}
        )

    def _register_user(self, index: int) -> tuple:
        """
        Register a single user via the API.

        Args:
            index: Unique index for generating email/org name

        Returns:
            Tuple of (status_code, elapsed_ms)
        """
        client = APIClient()
        response, elapsed = _timed_request(
            client,
            "post",
            "/v1/accounts/register/",
            data={
                "full_name": f"Load User {index}",
                "email": f"concurrent_reg_{index}@test.com",
                "organization": f"ConcurrentOrg{index}",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            format="json",
        )
        return response.status_code, elapsed

    def test_concurrent_registrations_succeed(self):
        """All concurrent registration requests should succeed."""
        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_REGISTRATIONS) as pool:
            futures = {
                pool.submit(_thread_safe(self._register_user), i): i
                for i in range(self.CONCURRENT_REGISTRATIONS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for code, _ in results if code == status.HTTP_201_CREATED)
        self.assertEqual(
            success_count,
            self.CONCURRENT_REGISTRATIONS,
            f"Only {success_count}/{self.CONCURRENT_REGISTRATIONS} registrations succeeded",
        )

    def test_registration_response_times(self):
        """Registration response times should be under threshold."""
        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_REGISTRATIONS) as pool:
            futures = {
                pool.submit(_thread_safe(self._register_user), i + 100): i
                for i in range(self.CONCURRENT_REGISTRATIONS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        times = [elapsed for _, elapsed in results]
        avg_time = sum(times) / len(times)
        max_time = max(times)
        self.assertLess(
            avg_time,
            BULK_RESPONSE_TIME_THRESHOLD_MS,
            f"Average registration time {avg_time:.0f}ms exceeds {BULK_RESPONSE_TIME_THRESHOLD_MS}ms",
        )
        self.assertLess(
            max_time,
            BULK_RESPONSE_TIME_THRESHOLD_MS * 3,
            f"Max registration time {max_time:.0f}ms exceeds {BULK_RESPONSE_TIME_THRESHOLD_MS * 3}ms",
        )


class TestConcurrentAuthentication(TransactionTestCase):
    """Tests concurrent login requests."""

    CONCURRENT_LOGINS = 10

    def setUp(self):
        Role.objects.get_or_create(
            id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"}
        )
        for i in range(self.CONCURRENT_LOGINS):
            UserModel.objects.create_user(
                email=f"loginuser{i}@test.com", password=TEST_PASSWORD
            )

    def _login_user(self, index: int) -> tuple:
        """
        Login a single user via JWT endpoint.

        Args:
            index: User index matching created users

        Returns:
            Tuple of (status_code, elapsed_ms)
        """
        client = APIClient()
        response, elapsed = _timed_request(
            client,
            "post",
            "/v1/accounts/login/",
            data={
                "email": f"loginuser{index}@test.com",
                "password": TEST_PASSWORD,
            },
            format="json",
        )
        return response.status_code, elapsed

    def test_concurrent_logins_succeed(self):
        """All concurrent login requests should succeed."""
        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_LOGINS) as pool:
            futures = {
                pool.submit(_thread_safe(self._login_user), i): i
                for i in range(self.CONCURRENT_LOGINS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for code, _ in results if code == status.HTTP_200_OK)
        self.assertEqual(
            success_count,
            self.CONCURRENT_LOGINS,
            f"Only {success_count}/{self.CONCURRENT_LOGINS} logins succeeded",
        )

    def test_login_response_times(self):
        """Login response times should be under threshold."""
        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_LOGINS) as pool:
            futures = {
                pool.submit(_thread_safe(self._login_user), i): i
                for i in range(self.CONCURRENT_LOGINS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        times = [elapsed for _, elapsed in results]
        avg_time = sum(times) / len(times)
        self.assertLess(
            avg_time,
            BULK_RESPONSE_TIME_THRESHOLD_MS,
            f"Average login time {avg_time:.0f}ms exceeds {BULK_RESPONSE_TIME_THRESHOLD_MS}ms",
        )


class TestConcurrentDatasetOperations(LoadTestBase):
    """Tests concurrent dataset CRUD operations."""

    def _create_dataset(self, client_index: int, dataset_index: int) -> tuple:
        """
        Create a dataset for a specific user via ORM and list datasets.

        Args:
            client_index: Index of the user/client to use
            dataset_index: Unique index for the dataset name

        Returns:
            Tuple of (status_code, elapsed_ms)
        """
        user = self.users[client_index]
        Dataset.objects.create(
            name=f"LoadDataset-{client_index}-{dataset_index}",
            org=user.organization,
        )
        client = self.clients[client_index]
        response, elapsed = _timed_request(
            client, "get", "/v1/api/uploads/datasets/"
        )
        return response.status_code, elapsed

    def test_concurrent_dataset_listing(self):
        """Concurrent dataset listing across users should succeed."""
        for i, user in enumerate(self.users):
            for j in range(5):
                Dataset.objects.create(
                    name=f"PreloadDS-{i}-{j}", org=user.organization
                )

        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = {
                pool.submit(
                    _thread_safe(lambda idx: _timed_request(
                        self.clients[idx], "get", "/v1/api/uploads/datasets/"
                    )),
                    i,
                ): i
                for i in range(self.CONCURRENT_USERS)
            }
            for future in as_completed(futures):
                resp, elapsed = future.result()
                results.append((resp.status_code, elapsed))

        success_count = sum(1 for code, _ in results if code == status.HTTP_200_OK)
        self.assertEqual(success_count, self.CONCURRENT_USERS)

    def test_concurrent_dataset_creation_and_listing(self):
        """Mixed create-then-list operations across users should succeed."""
        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = []
            for i in range(self.CONCURRENT_USERS):
                for j in range(3):
                    futures.append(pool.submit(_thread_safe(self._create_dataset), i, j))
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(
            1 for code, _ in results if code == status.HTTP_200_OK
        )
        self.assertEqual(success_count, self.CONCURRENT_USERS * 3)

    def test_dataset_listing_response_time_scales(self):
        """Response time should be acceptable even with many datasets."""
        user = self.users[0]
        client = self.clients[0]

        for i in range(50):
            Dataset.objects.create(
                name=f"ScaleDS-{i}", org=user.organization
            )

        _, elapsed = _timed_request(client, "get", "/v1/api/uploads/datasets/")
        self.assertLess(
            elapsed,
            BULK_RESPONSE_TIME_THRESHOLD_MS,
            f"Dataset listing with 50 items took {elapsed:.0f}ms",
        )


class TestConcurrentJobOperations(LoadTestBase):
    """Tests concurrent job-related operations."""

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret-key")
    def test_concurrent_job_listing(self):
        """Concurrent job listing across multiple users should succeed."""
        for i, user in enumerate(self.users):
            ds = Dataset.objects.create(
                name=f"JobDS-{i}", org=user.organization
            )
            for j in range(3):
                ProcessingJob.objects.create(
                    dataset=ds,
                    resolution_gsd=5.0,
                    status=JobStatus.COMPLETED,
                    stage=ProcessingStage.COMPLETED,
                    progress=100,
                )

        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = {
                pool.submit(
                    _thread_safe(lambda idx: _timed_request(
                        self.clients[idx], "get", "/v1/api/jobs/"
                    )),
                    i,
                ): i
                for i in range(self.CONCURRENT_USERS)
            }
            for future in as_completed(futures):
                resp, elapsed = future.result()
                results.append((resp.status_code, elapsed))

        success_count = sum(1 for code, _ in results if code == status.HTTP_200_OK)
        self.assertEqual(success_count, self.CONCURRENT_USERS)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret-key")
    def test_concurrent_job_detail_reads(self):
        """Concurrent reads of the same job should succeed."""
        user = self.users[0]
        client = self.clients[0]
        ds = Dataset.objects.create(name="DetailDS", org=user.organization)
        job = ProcessingJob.objects.create(
            dataset=ds,
            resolution_gsd=5.0,
            status=JobStatus.PROCESSING,
            stage=ProcessingStage.SFM,
            progress=50,
        )

        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = {
                pool.submit(
                    _thread_safe(lambda _: _timed_request(
                        client,
                        "get",
                        f"/v1/api/jobs/{job.id}/",
                    )),
                    i,
                ): i
                for i in range(self.CONCURRENT_USERS)
            }
            for future in as_completed(futures):
                resp, elapsed = future.result()
                results.append((resp.status_code, elapsed))

        success_count = sum(1 for code, _ in results if code == status.HTTP_200_OK)
        self.assertEqual(success_count, self.CONCURRENT_USERS)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret-key")
    def test_concurrent_ai_callbacks(self):
        """Concurrent AI callback updates should not corrupt data."""
        user = self.users[0]
        ds = Dataset.objects.create(name="CallbackDS", org=user.organization)
        jobs = []
        for i in range(self.CONCURRENT_USERS):
            job = ProcessingJob.objects.create(
                dataset=ds,
                resolution_gsd=5.0,
                status=JobStatus.PROCESSING,
                stage=ProcessingStage.SFM,
                progress=10,
            )
            jobs.append(job)

        def send_callback(index: int) -> tuple:
            """
            Send a progress callback for a specific job.

            Args:
                index: Job index to update

            Returns:
                Tuple of (status_code, elapsed_ms)
            """
            client = APIClient()
            response, elapsed = _timed_request(
                client,
                "post",
                "/v1/api/jobs/ai-callback/",
                data={
                    "job_id": str(jobs[index].id),
                    "type": "progress",
                    "current_stage": ProcessingStage.ORTHOMOSAIC,
                    "progress": 50.0 + index,
                    "message": f"Processing update {index}",
                },
                format="json",
                HTTP_X_API_SECRET_KEY="test-secret-key",
            )
            return response.status_code, elapsed

        results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = {
                pool.submit(_thread_safe(send_callback), i): i
                for i in range(self.CONCURRENT_USERS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        success_count = sum(1 for code, _ in results if code == status.HTTP_200_OK)
        self.assertEqual(success_count, self.CONCURRENT_USERS)

        for i, job in enumerate(jobs):
            job.refresh_from_db()
            self.assertEqual(job.stage, ProcessingStage.ORTHOMOSAIC)


class TestCrossOrgIsolationUnderLoad(LoadTestBase):
    """Tests that cross-organization isolation holds under concurrent access."""

    def test_users_only_see_own_datasets_under_load(self):
        """Each user should only see their own datasets under concurrent access."""
        for i, user in enumerate(self.users):
            for j in range(5):
                Dataset.objects.create(
                    name=f"IsolationDS-{i}-{j}", org=user.organization
                )

        results = {}

        def list_datasets(index: int) -> tuple:
            """
            List datasets for a specific user client.

            Args:
                index: Index of the user/client

            Returns:
                Tuple of (user_index, dataset_count, dataset_names)
            """
            response = self.clients[index].get("/v1/api/uploads/datasets/")
            data = response.data.get("results", response.data)
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            if isinstance(data, list):
                names = [d.get("name", "") for d in data]
            else:
                names = []
            return index, len(names), names

        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = {
                pool.submit(_thread_safe(list_datasets), i): i
                for i in range(self.CONCURRENT_USERS)
            }
            for future in as_completed(futures):
                idx, count, names = future.result()
                results[idx] = (count, names)

        for i in range(self.CONCURRENT_USERS):
            count, names = results[i]
            self.assertEqual(
                count,
                5,
                f"User {i} saw {count} datasets instead of 5: {names}",
            )
            for name in names:
                self.assertIn(
                    f"IsolationDS-{i}-",
                    name,
                    f"User {i} saw dataset '{name}' not belonging to them",
                )


class TestAPIResponseTimeThresholds(TestCase):
    """Tests that key API endpoints respond within acceptable time limits."""

    def setUp(self):
        Role.objects.get_or_create(
            id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"}
        )
        Role.objects.get_or_create(
            id=2, defaults={"name": RoleName.USER, "label": "Owner"}
        )
        self.client = APIClient()
        self.user = UserModel.objects.create_user(
            email="perf@test.com", password=TEST_PASSWORD
        )
        self.org = Organization.objects.create(name="PerfOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_dataset_list_response_time(self):
        """Dataset list endpoint should respond under threshold."""
        for i in range(10):
            Dataset.objects.create(name=f"PerfDS-{i}", org=self.org)

        _, elapsed = _timed_request(
            self.client, "get", "/v1/api/uploads/datasets/"
        )
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Dataset list took {elapsed:.0f}ms",
        )

    def test_dataset_detail_response_time(self):
        """Dataset detail endpoint should respond under threshold."""
        ds = Dataset.objects.create(name="PerfDetailDS", org=self.org)
        _, elapsed = _timed_request(
            self.client, "get", f"/v1/api/uploads/datasets/{ds.id}/"
        )
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Dataset detail took {elapsed:.0f}ms",
        )

    def test_job_list_response_time(self):
        """Job list endpoint should respond under threshold."""
        ds = Dataset.objects.create(name="PerfJobDS", org=self.org)
        for i in range(10):
            ProcessingJob.objects.create(
                dataset=ds,
                resolution_gsd=5.0,
                status=JobStatus.COMPLETED,
                stage=ProcessingStage.COMPLETED,
                progress=100,
            )

        _, elapsed = _timed_request(self.client, "get", "/v1/api/jobs/")
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Job list took {elapsed:.0f}ms",
        )

    def test_job_detail_response_time(self):
        """Job detail endpoint should respond under threshold."""
        ds = Dataset.objects.create(name="PerfJobDetailDS", org=self.org)
        job = ProcessingJob.objects.create(
            dataset=ds,
            resolution_gsd=5.0,
            status=JobStatus.PROCESSING,
            stage=ProcessingStage.SFM,
            progress=50,
        )
        _, elapsed = _timed_request(
            self.client, "get", f"/v1/api/jobs/{job.id}/"
        )
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Job detail took {elapsed:.0f}ms",
        )

    def test_product_list_response_time(self):
        """Product list endpoint should respond under threshold."""
        ds = Dataset.objects.create(name="PerfProdDS", org=self.org)
        job = ProcessingJob.objects.create(
            dataset=ds,
            resolution_gsd=5.0,
            status=JobStatus.COMPLETED,
            stage=ProcessingStage.COMPLETED,
            progress=100,
        )
        for i in range(10):
            Product.objects.create(
                dataset=ds,
                job=job,
                type="orthomosaic",
                uri=f"s3://bucket/ortho_{i}.tif",
            )

        _, elapsed = _timed_request(self.client, "get", "/v1/api/products/")
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Product list took {elapsed:.0f}ms",
        )

    def test_dashboard_stats_response_time(self):
        """Dashboard stats endpoint should respond under threshold."""
        _, elapsed = _timed_request(
            self.client, "get", "/v1/api/dashboard/stats/"
        )
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Dashboard stats took {elapsed:.0f}ms",
        )

    def test_profile_response_time(self):
        """Profile endpoint should respond under threshold."""
        _, elapsed = _timed_request(
            self.client, "get", "/v1/accounts/profile/"
        )
        self.assertLess(
            elapsed,
            RESPONSE_TIME_THRESHOLD_MS,
            f"Profile endpoint took {elapsed:.0f}ms",
        )


class TestDatabaseScaling(TestCase):
    """Tests database performance with growing data volumes."""

    def setUp(self):
        Role.objects.get_or_create(
            id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"}
        )
        Role.objects.get_or_create(
            id=2, defaults={"name": RoleName.USER, "label": "Owner"}
        )
        self.client = APIClient()
        self.user = UserModel.objects.create_user(
            email="scale@test.com", password=TEST_PASSWORD
        )
        self.org = Organization.objects.create(name="ScaleOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_dataset_list_scales_with_100_records(self):
        """Dataset listing should remain fast with 100 records."""
        Dataset.objects.bulk_create(
            [
                Dataset(name=f"BulkDS-{i}", org=self.org)
                for i in range(100)
            ]
        )

        _, elapsed = _timed_request(
            self.client, "get", "/v1/api/uploads/datasets/"
        )
        self.assertLess(
            elapsed,
            BULK_RESPONSE_TIME_THRESHOLD_MS,
            f"Listing 100 datasets took {elapsed:.0f}ms",
        )

    def test_job_list_scales_with_100_records(self):
        """Job listing should remain fast with 100 records."""
        ds = Dataset.objects.create(name="BulkJobDS", org=self.org)
        ProcessingJob.objects.bulk_create(
            [
                ProcessingJob(
                    dataset=ds,
                    resolution_gsd=5.0,
                    status=JobStatus.COMPLETED,
                    stage=ProcessingStage.COMPLETED,
                    progress=100,
                )
                for _ in range(100)
            ]
        )

        _, elapsed = _timed_request(self.client, "get", "/v1/api/jobs/")
        self.assertLess(
            elapsed,
            BULK_RESPONSE_TIME_THRESHOLD_MS,
            f"Listing 100 jobs took {elapsed:.0f}ms",
        )

    def test_product_list_scales_with_100_records(self):
        """Product listing should remain fast with 100 records."""
        ds = Dataset.objects.create(name="BulkProdDS", org=self.org)
        job = ProcessingJob.objects.create(
            dataset=ds,
            resolution_gsd=5.0,
            status=JobStatus.COMPLETED,
            stage=ProcessingStage.COMPLETED,
            progress=100,
        )
        Product.objects.bulk_create(
            [
                Product(
                    dataset=ds,
                    job=job,
                    type="orthomosaic",
                    uri=f"s3://bucket/bulk_{i}.tif",
                )
                for i in range(100)
            ]
        )

        _, elapsed = _timed_request(self.client, "get", "/v1/api/products/")
        self.assertLess(
            elapsed,
            BULK_RESPONSE_TIME_THRESHOLD_MS,
            f"Listing 100 products took {elapsed:.0f}ms",
        )


class TestRapidFireRequests(TestCase):
    """Tests rapid sequential requests to detect connection/resource leaks."""

    RAPID_FIRE_COUNT = 50

    def setUp(self):
        Role.objects.get_or_create(
            id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"}
        )
        self.client = APIClient()
        self.user = UserModel.objects.create_user(
            email="rapid@test.com", password=TEST_PASSWORD
        )
        self.org = Organization.objects.create(name="RapidOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()
        self.client.force_authenticate(user=self.user)

        for i in range(5):
            Dataset.objects.create(name=f"RapidDS-{i}", org=self.org)

    def test_rapid_dataset_listing(self):
        """Rapid sequential dataset list requests should all succeed."""
        failures = 0
        times = []
        for _ in range(self.RAPID_FIRE_COUNT):
            resp, elapsed = _timed_request(
                self.client, "get", "/v1/api/uploads/datasets/"
            )
            times.append(elapsed)
            if resp.status_code != status.HTTP_200_OK:
                failures += 1

        self.assertEqual(failures, 0, f"{failures} out of {self.RAPID_FIRE_COUNT} requests failed")

        avg_time = sum(times) / len(times)
        degradation = times[-1] / max(times[0], 0.01)
        self.assertLess(
            degradation,
            5.0,
            f"Response time degraded {degradation:.1f}x (first={times[0]:.0f}ms, last={times[-1]:.0f}ms)",
        )

    def test_rapid_profile_access(self):
        """Rapid sequential profile requests should all succeed."""
        failures = 0
        for _ in range(self.RAPID_FIRE_COUNT):
            resp, _ = _timed_request(
                self.client, "get", "/v1/accounts/profile/"
            )
            if resp.status_code != status.HTTP_200_OK:
                failures += 1

        self.assertEqual(failures, 0, f"{failures} out of {self.RAPID_FIRE_COUNT} requests failed")


class TestMixedWorkloadConcurrency(LoadTestBase):
    """Tests realistic mixed read/write workloads under concurrency."""

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret-key")
    def test_mixed_read_write_operations(self):
        """Mixed read and write operations across users should not conflict."""
        for i, user in enumerate(self.users):
            ds = Dataset.objects.create(
                name=f"MixedDS-{i}", org=user.organization
            )
            ProcessingJob.objects.create(
                dataset=ds,
                resolution_gsd=5.0,
                status=JobStatus.COMPLETED,
                stage=ProcessingStage.COMPLETED,
                progress=100,
            )

        def mixed_operation(index: int) -> list:
            """
            Perform a mix of read operations for a specific user.

            Args:
                index: Index of the user/client

            Returns:
                List of (operation_name, status_code) tuples
            """
            client = self.clients[index]
            results = []

            resp, _ = _timed_request(
                client, "get", "/v1/api/uploads/datasets/"
            )
            results.append(("dataset_list", resp.status_code))

            resp, _ = _timed_request(client, "get", "/v1/api/jobs/")
            results.append(("job_list", resp.status_code))

            resp, _ = _timed_request(client, "get", "/v1/accounts/profile/")
            results.append(("profile", resp.status_code))

            Dataset.objects.create(
                name=f"MixedNewDS-{index}-{uuid.uuid4().hex[:6]}",
                org=self.users[index].organization,
            )
            resp, _ = _timed_request(
                client, "get", "/v1/api/uploads/datasets/"
            )
            results.append(("dataset_list_after_create", resp.status_code))

            return results

        all_results = []
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as pool:
            futures = {
                pool.submit(_thread_safe(mixed_operation), i): i
                for i in range(self.CONCURRENT_USERS)
            }
            for future in as_completed(futures):
                all_results.extend(future.result())

        failures = [
            (op, code)
            for op, code in all_results
            if code != status.HTTP_200_OK
        ]
        self.assertEqual(
            len(failures),
            0,
            f"Failed operations under mixed workload: {failures}",
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
