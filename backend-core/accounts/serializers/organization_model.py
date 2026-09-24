from rest_framework import serializers

from accounts.models.organization import Organization
from accounts.serializers.user import AccountUserModelSerializer


class OrganizationModelSerializer(serializers.ModelSerializer):
    user = AccountUserModelSerializer()

    class Meta:
        model = Organization
        fields = "__all__"
