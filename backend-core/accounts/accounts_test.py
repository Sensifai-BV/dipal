from django.test import TestCase
from unittest.mock import MagicMock
from django.http import QueryDict
from accounts.models.user import UserModel
from accounts.models.organization import Organization
from accounts.services.organization import OrganizationQueryService


class OrganizationQueryServiceTest(TestCase):
    def setUp(self):

        self.user = UserModel.objects.create(
            email="test@example.com",
            password="password123"
        )
        self.other_user = UserModel.objects.create(
            email="other@example.com",
            password="password123"
        )


        self.org1 = Organization.objects.create(name="Alpha Corp", user=self.user)
        self.org2 = Organization.objects.create(name="Beta Ltd", user=self.user)


        self.other_org = Organization.objects.create(name="Other Inc", user=self.other_user)


        self.mock_logging_config = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_logging_config.get_logger.return_value = self.mock_logger


        self.service = OrganizationQueryService(logging_config=self.mock_logging_config)

    def test_all_filtered_queryset_returns_user_organizations(self):

        query_params = QueryDict('')
        result = self.service.all_filtered_queryset(user=self.user, query_params=query_params)

        self.assertEqual(result.count(), 2)
        self.assertIn(self.org1, result)
        self.assertIn(self.org2, result)
        self.assertNotIn(self.other_org, result)  #      

    def test_get_filtered_queryset_found(self):

        query_params = QueryDict('')

        result = self.service.get_filtered_queryset(
            user=self.user,
            object_id=self.org1.id,
            query_params=query_params
        )

        self.assertIsNotNone(result)
        self.assertEqual(result, self.org1)

        self.mock_logger.info.assert_called()

    def test_get_filtered_queryset_not_found_wrong_id(self):

        import uuid
        random_uuid = uuid.uuid4()
        query_params = QueryDict('')

        result = self.service.get_filtered_queryset(
            user=self.user,
            object_id=random_uuid,
            query_params=query_params
        )

        self.assertIsNone(result)
        self.mock_logger.warning.assert_called()

    def test_get_filtered_queryset_not_found_wrong_user(self):

        query_params = QueryDict('')


        result = self.service.get_filtered_queryset(
            user=self.user,
            object_id=self.other_org.id,
            query_params=query_params
        )

        self.assertIsNone(result)

    def test_apply_ordering(self):

        queryset = Organization.objects.filter(user=self.user)


        ordered_qs = self.service.apply_ordering(queryset=queryset, ordering_param='name')


        self.assertEqual(ordered_qs.first(), self.org1)
        self.assertEqual(ordered_qs.last(), self.org2)


        ordered_qs_desc = self.service.apply_ordering(queryset=queryset, ordering_param='-name')
        self.assertEqual(ordered_qs_desc.first(), self.org2)
