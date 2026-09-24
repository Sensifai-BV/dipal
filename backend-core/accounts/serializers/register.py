from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.db import transaction
from accounts.models.user import UserModel
from accounts.models.organization import Organization
from accounts.models.role import Role


class AccountRegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(required=True)
    organization = serializers.CharField(required=True)

    role = serializers.IntegerField(required=False, default=1)

    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):

        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'password': 'Passwords do not match'})


        role_id = attrs.get('role')
        try:

            role_obj = Role.objects.get(id=role_id)
            attrs['role'] = role_obj
        except Role.DoesNotExist:

            raise serializers.ValidationError({
                'role': f"Role with id {role_id} does not exist."
            })


        full_name = attrs.pop('full_name').strip()
        if ' ' in full_name:
            first, last = full_name.split(' ', 1)
            attrs['first_name'] = first
            attrs['last_name'] = last
        else:
            attrs['first_name'] = full_name
            attrs['last_name'] = ''

        return attrs

    def create(self, validated_data):
        org_name = validated_data.pop('organization')
        validated_data.pop('confirm_password')

        validated_data['password'] = make_password(validated_data['password'])

        try:
            with transaction.atomic():

                user = UserModel.objects.create(**validated_data)


                org, created = Organization.objects.get_or_create(
                    name=org_name,
                    defaults = {'user': user}
                )

                user.organization = org
                user.save()

                return user

        except Exception as e:
            raise serializers.ValidationError({
                "detail": f"Database Error: {str(e)}"
            })
