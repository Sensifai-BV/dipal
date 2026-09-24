from adrf.serializers import Serializer
from rest_framework import serializers

from accounts.models.organization import Organization


class OrganizationCreateInputSerializer(Serializer):
    name = serializers.CharField(
        max_length=100,
        min_length=3,
        required=True,
    )
    description = serializers.CharField(
        required=False,
    )

    async def create(self, validated_data):
        user = self.context['user']
        orgs_obj = await Organization.objects.acreate(
            user=user,
            **validated_data
        )

        return orgs_obj
