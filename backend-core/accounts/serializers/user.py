from adrf.serializers import ModelSerializer
from rest_framework import serializers
from accounts.models.user import UserModel


class AccountUserModelSerializer(ModelSerializer):

    class Meta:
        model = UserModel
        fields = [
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'role',
            'organization',
            'is_email_verified',
        ]
        read_only_fields = ['id', 'username', 'is_email_verified']
